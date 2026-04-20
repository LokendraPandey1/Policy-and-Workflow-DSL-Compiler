import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.compiler import compile_dsl
from src.interpreter import Interpreter
from src.lexer import Lexer
from src.nlp_parser import convert_nl_to_dsl
from src.parser import Parser
from src.semantic import SemanticAnalyzer


BASE_DIR = Path(__file__).resolve().parent

ENROLLMENT_SAMPLE_DSL = """
policy StudentEligibility {
    input gpa: number
    input credits: number
    input is_enrolled: boolean

    rule min_gpa: gpa >= 3.0
    rule min_credits: credits >= 30
    rule active: is_enrolled == true

    evaluate: min_gpa AND min_credits AND active
}

workflow EnrollmentProcess {
    step CheckEligibility {
        execute policy StudentEligibility
        on pass -> next
        on fail -> reject "Student does not meet requirements"
    }

    step NotifyStudent {
        action "Send enrollment confirmation email"
        on complete -> done
    }
}
""".strip()


LOAN_SAMPLE_NL = """
Create a policy called CreditCheck that takes inputs for credit_score, annual_income, and existing_debt.
The policy should pass if the credit score is at least 700, the annual income is at least 30000, and existing debt is less than 10000.
Also create a policy called IdentityVerification that takes a boolean has_valid_id and a number age.
It passes if they have a valid ID and are at least 18 years old.
Now make a workflow called LoanApproval.
First step is VerifyIdentity which executes the IdentityVerification policy. If it passes, go to the next step, if it fails reject with "Identity verification failed".
The next step CheckCredit executes the CreditCheck policy. On pass go to next, on fail reject with "Credit check failed".
Then step CalculateTerms performs an action to "Calculate loan interest rate". On complete go to next.
Finally, step DisburseFunds performs an action to "Transfer approved amount". On complete, the workflow is done.
""".strip()


SERVER_SAMPLE_NL = """
Create a ServerHealth policy. Inputs are cpu_usage, memory_usage, disk_usage, and a boolean is_responsive.
Rules:
- cpu is under 90
- memory is under 85
- disk is under 80
- server is responsive
Evaluate that all rules are true.
Then create an IncidentResponse workflow.
First step CheckHealth executes ServerHealth policy. If it passes, go to the next step. If it fails, reject with "Server offline".
Step LogStatus performs an action "Log metrics". Complete -> next.
Step ClearAlert performs action "Mark healthy". Complete -> done.
""".strip()


PHASE_SPECS = [
    {"key": "lexer", "number": "01", "title": "Lexer", "subtitle": "Token stream"},
    {"key": "parser", "number": "02", "title": "Parser", "subtitle": "AST structure"},
    {"key": "semantic", "number": "03", "title": "Semantic", "subtitle": "Validation and symbols"},
    {"key": "codegen", "number": "04", "title": "Code Gen", "subtitle": "Python output"},
    {"key": "runtime", "number": "05", "title": "Runtime", "subtitle": "Execution trace"},
]


SAMPLES = {
    "enrollment_dsl": {
        "label": "Enrollment DSL",
        "type": "dsl",
        "content": ENROLLMENT_SAMPLE_DSL,
    },
    "loan_brief": {
        "label": "Loan Brief",
        "type": "nl",
        "content": LOAN_SAMPLE_NL,
    },
    "server_brief": {
        "label": "Server Brief",
        "type": "nl",
        "content": SERVER_SAMPLE_NL,
    },
}


app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))


def build_program(source: str):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def collect_runtime_targets(ast_dict: dict) -> list[dict]:
    policies = {policy["name"]: policy for policy in ast_dict.get("policies", [])}
    targets = []

    for workflow in ast_dict.get("workflows", []):
        input_map = {}
        for step in workflow.get("steps", []):
            execute = step.get("execute")
            if not execute:
                continue
            policy_name = execute.get("policy_name")
            for input_decl in policies.get(policy_name, {}).get("inputs", []):
                input_map[input_decl["name"]] = input_decl["type"]
        targets.append(
            {
                "kind": "workflow",
                "name": workflow["name"],
                "label": f"Workflow: {workflow['name']}",
                "inputs": [{"name": key, "type": value} for key, value in input_map.items()],
            }
        )

    for policy in ast_dict.get("policies", []):
        targets.append(
            {
                "kind": "policy",
                "name": policy["name"],
                "label": f"Policy: {policy['name']}",
                "inputs": policy.get("inputs", []),
            }
        )

    return targets


def summarize_program(result: dict) -> list[str]:
    ast_dict = result.get("ast") or {}
    policies = ast_dict.get("policies", [])
    workflows = ast_dict.get("workflows", [])
    semantic = result.get("semantic", {})

    lines = [
        "Project analysis",
        "",
        "This compiler is organized as a real five-phase pipeline:",
        "1. Lexer tokenizes DSL source with line and column tracking.",
        "2. Parser builds an AST for policies, workflows, steps, and expressions.",
        "3. Semantic analysis validates declarations, references, and type consistency.",
        "4. Code generation emits runnable Python from the validated program model.",
        "5. Runtime interpretation evaluates policies and executes workflows with trace events.",
        "",
        "Current program snapshot",
        f"- Policies discovered: {len(policies)}",
        f"- Workflows discovered: {len(workflows)}",
        f"- Semantic status: {'valid' if semantic.get('valid') else 'issues found'}",
        f"- Generated code lines: {len(result.get('generated_code', '').splitlines()) if result.get('generated_code') else 0}",
    ]

    if policies:
        lines.append("")
        lines.append("Policy inventory")
        for policy in policies:
            lines.append(
                f"- {policy['name']}: {len(policy.get('inputs', []))} input(s), {len(policy.get('rules', []))} rule(s)"
            )

    if workflows:
        lines.append("")
        lines.append("Workflow inventory")
        for workflow in workflows:
            lines.append(f"- {workflow['name']}: {len(workflow.get('steps', []))} step(s)")

    execution = result.get("execution")
    lines.append("")
    if execution:
        runtime_status = execution.get("status", "policy evaluation complete")
        lines.append(f"Latest runtime result: {runtime_status}")
        lines.append(f"Message: {execution.get('message', execution.get('passed', 'n/a'))}")
    else:
        lines.append("Latest runtime result: not executed yet")

    return lines


def build_phase_states(result: dict) -> dict:
    states = {
        "lexer": {"status": "Waiting", "tone": "idle"},
        "parser": {"status": "Waiting", "tone": "idle"},
        "semantic": {"status": "Waiting", "tone": "idle"},
        "codegen": {"status": "Waiting", "tone": "idle"},
        "runtime": {"status": "Waiting", "tone": "idle"},
    }

    errors = result.get("errors", [])
    if errors:
        failed_stage = errors[0].get("stage", "lexer")
        if failed_stage == "lexer":
            states["lexer"] = {"status": "Failed", "tone": "danger"}
            states["parser"] = {"status": "Blocked", "tone": "idle"}
        elif failed_stage == "parser":
            states["lexer"] = {"status": f"{len(result.get('tokens', []))} tokens", "tone": "ok"}
            states["parser"] = {"status": "Failed", "tone": "danger"}
        states["semantic"] = {"status": "Blocked", "tone": "idle"}
        states["codegen"] = {"status": "Blocked", "tone": "idle"}
        states["runtime"] = {"status": "Blocked", "tone": "idle"}
        return states

    states["lexer"] = {"status": f"{len(result.get('tokens', []))} tokens", "tone": "ok"}
    states["parser"] = {"status": "AST ready", "tone": "ok"}

    semantic = result.get("semantic", {})
    if semantic.get("valid"):
        states["semantic"] = {"status": "Valid", "tone": "ok"}
    else:
        states["semantic"] = {
            "status": f"{len(semantic.get('errors', []))} issue(s)",
            "tone": "danger",
        }

    if result.get("generated_code"):
        states["codegen"] = {"status": "Generated", "tone": "ok"}
    else:
        states["codegen"] = {"status": "No output", "tone": "warn"}

    if result.get("execution"):
        states["runtime"] = {"status": "Executed", "tone": "ok"}
    elif semantic.get("valid"):
        states["runtime"] = {"status": "Ready", "tone": "warn"}
    else:
        states["runtime"] = {"status": "Blocked", "tone": "danger"}

    return states


def build_metrics(source: str, result: dict | None) -> dict:
    metrics = {
        "source_lines": len(source.splitlines()) if source else 0,
        "token_count": "--",
        "policy_count": "--",
        "workflow_count": "--",
        "semantic_state": "--",
        "runtime_state": "--",
    }

    if not result:
        return metrics

    ast_dict = result.get("ast") or {}
    metrics["token_count"] = len(result.get("tokens", []))
    metrics["policy_count"] = len(ast_dict.get("policies", []))
    metrics["workflow_count"] = len(ast_dict.get("workflows", []))
    metrics["semantic_state"] = "Valid" if result.get("semantic", {}).get("valid") else "Needs fixes"

    execution = result.get("execution")
    if execution:
        metrics["runtime_state"] = execution.get("status", "Evaluated")
    elif result.get("semantic", {}).get("valid"):
        metrics["runtime_state"] = "Ready"
    else:
        metrics["runtime_state"] = "Blocked"

    return metrics


def build_semantic_report(result: dict) -> str:
    semantic = result.get("semantic", {})
    if semantic.get("valid"):
        return "Semantic analysis passed.\n\nNo static validation errors were found."
    if semantic.get("errors"):
        return "Semantic analysis found issues:\n\n" + "\n".join(
            f"- {item['message']} (line {item.get('line', 'unknown')})"
            for item in semantic["errors"]
        )
    return "Semantic analysis did not run."


def build_runtime_report(execution: dict | None) -> str:
    if not execution:
        return "Runtime not executed yet.\n\nCompile a valid program and then run a policy or workflow target with input values."

    if "passed" in execution:
        lines = [f"Policy passed: {execution['passed']}", "", "Rule results:"]
        for name, passed in execution.get("rules", {}).items():
            lines.append(f"- {name}: {passed}")
        return "\n".join(lines)

    return "\n".join(
        [
            f"Workflow status: {execution.get('status', 'unknown')}",
            f"Message: {execution.get('message', '')}",
        ]
    )


def build_payload(source: str, result: dict, message: str) -> dict:
    ast_dict = result.get("ast") or {}
    return {
        "ok": not bool(result.get("errors")),
        "message": message,
        "result": result,
        "runtime_targets": collect_runtime_targets(ast_dict),
        "phase_states": build_phase_states(result),
        "metrics": build_metrics(source, result),
        "overview_lines": summarize_program(result),
        "semantic_report": build_semantic_report(result),
        "runtime_report": build_runtime_report(result.get("execution")),
    }


@app.get("/")
def index():
    return render_template(
        "index.html",
        phase_specs=PHASE_SPECS,
        samples=SAMPLES,
        initial_source=ENROLLMENT_SAMPLE_DSL,
        initial_nl=LOAN_SAMPLE_NL,
    )


@app.get("/api/samples")
def get_samples():
    return jsonify({"samples": SAMPLES, "phase_specs": PHASE_SPECS})


@app.post("/api/translate")
def translate():
    payload = request.get_json(silent=True) or {}
    nl_text = (payload.get("text") or "").strip()
    if not nl_text:
        return jsonify({"ok": False, "message": "Add a plain English description before translating."}), 400

    converted_dsl, err = convert_nl_to_dsl(nl_text)
    if err:
        return jsonify({"ok": False, "message": err}), 400

    return jsonify(
        {
            "ok": True,
            "message": "Plain English brief translated into DSL.",
            "dsl": converted_dsl,
        }
    )


@app.post("/api/compile")
def compile_route():
    payload = request.get_json(silent=True) or {}
    source = (payload.get("source") or "").strip()
    if not source:
        return jsonify({"ok": False, "message": "The DSL editor is empty."}), 400

    result = compile_dsl(source)
    response = build_payload(source, result, "Compilation complete. Each phase now reflects the latest compiler state.")
    status_code = 200 if response["ok"] else 400
    return jsonify(response), status_code


@app.post("/api/run")
def run_route():
    payload = request.get_json(silent=True) or {}
    source = (payload.get("source") or "").strip()
    target = payload.get("target") or {}
    inputs = payload.get("inputs") or {}

    if not source:
        return jsonify({"ok": False, "message": "The DSL editor is empty."}), 400

    result = compile_dsl(source)
    if result.get("errors"):
        response = build_payload(source, result, "Fix lexer/parser errors before execution.")
        response["ok"] = False
        return jsonify(response), 400

    if not result.get("semantic", {}).get("valid"):
        response = build_payload(source, result, "Fix semantic issues before execution.")
        response["ok"] = False
        return jsonify(response), 400

    if not target or not target.get("kind") or not target.get("name"):
        response = build_payload(source, result, "Choose a policy or workflow target before running.")
        response["ok"] = False
        return jsonify(response), 400

    try:
        program = build_program(source)
        analyzer_errors = SemanticAnalyzer().analyze(program)
        if analyzer_errors:
            raise ValueError("Semantic issues remain in the current program.")

        interpreter = Interpreter(program)
        if target["kind"] == "workflow":
            execution = interpreter.run_workflow(target["name"], inputs)
        else:
            execution = interpreter.evaluate_policy(target["name"], inputs)
        result["execution"] = execution
    except Exception as exc:
        response = build_payload(source, result, str(exc))
        response["ok"] = False
        return jsonify(response), 400

    response = build_payload(source, result, f"{target['kind'].title()} '{target['name']}' executed successfully.")
    return jsonify(response)


def main():
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
