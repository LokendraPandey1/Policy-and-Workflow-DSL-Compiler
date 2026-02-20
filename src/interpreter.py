"""
Interpreter for the Policy & Workflow DSL.

Traverses the AST to:
  - Evaluate policies given input values → returns pass/fail with per-rule details
  - Execute workflows step-by-step, following transitions based on policy outcomes
  - Produce a detailed execution trace for visualization
"""

from typing import Dict, List, Any, Optional
from src.ast_nodes import (
    Program, Policy, InputDecl, RuleDecl, EvaluateStmt,
    Workflow, Step, Transition, ExecuteStmt, ActionStmt,
    BinaryOp, UnaryOp, LogicOp, Literal, Identifier, ASTNode,
)


# ── Execution Error ───────────────────────────────────────────────────────────

class ExecutionError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


# ── Trace Events ──────────────────────────────────────────────────────────────

class TraceEvent:
    """A single event in the execution trace."""
    def __init__(self, event_type: str, message: str, details: dict = None):
        self.event_type = event_type   # "info", "rule", "policy", "action", "transition", "result"
        self.message = message
        self.details = details or {}

    def to_dict(self):
        d = {"type": self.event_type, "message": self.message}
        if self.details:
            d["details"] = self.details
        return d


# ── Interpreter ───────────────────────────────────────────────────────────────

class Interpreter:
    """
    AST-walking interpreter for the DSL.

    Usage:
        interp = Interpreter(program_ast)
        result = interp.run_workflow("EnrollmentProcess", {
            "gpa": 3.5, "credits": 45, "is_enrolled": True
        })
    """

    def __init__(self, program: Program):
        self.program = program
        self.policies: Dict[str, Policy] = {p.name: p for p in program.policies}
        self.workflows: Dict[str, Workflow] = {w.name: w for w in program.workflows}
        self.trace: List[TraceEvent] = []

    # ── Public API ────────────────────────────────────────────────────────

    def evaluate_policy(self, policy_name: str, inputs: Dict[str, Any]) -> dict:
        """
        Evaluate a policy with the given inputs.
        Returns: {"passed": bool, "rules": {name: bool}, "trace": [...]}
        """
        self.trace = []
        policy = self.policies.get(policy_name)
        if not policy:
            raise ExecutionError(f"Policy '{policy_name}' not found")

        self._trace("info", f"Evaluating policy '{policy_name}'")

        # Build environment from declared inputs
        env = {}
        for inp in policy.inputs:
            if inp.name not in inputs:
                raise ExecutionError(
                    f"Missing input '{inp.name}' for policy '{policy_name}'"
                )
            env[inp.name] = self._coerce_input(inputs[inp.name], inp.type, inp.name)
            self._trace("info", f"  Input {inp.name} = {env[inp.name]}")

        # Evaluate each rule
        rule_results = {}
        for rule in policy.rules:
            result = self._eval_expr(rule.expression, env)
            rule_results[rule.name] = bool(result)
            status = "✓ PASS" if result else "✗ FAIL"
            self._trace("rule", f"  Rule '{rule.name}': {status}", {"rule": rule.name, "result": bool(result)})

        # Build rule environment for evaluate expression
        eval_env = {**env, **rule_results}

        # Evaluate the final expression
        passed = bool(self._eval_expr(policy.evaluate.expression, eval_env))
        status = "✓ PASSED" if passed else "✗ FAILED"
        self._trace("policy", f"Policy '{policy_name}': {status}", {"policy": policy_name, "passed": passed})

        return {
            "passed": passed,
            "rules": rule_results,
            "trace": [t.to_dict() for t in self.trace],
        }

    def run_workflow(self, workflow_name: str, inputs: Dict[str, Any]) -> dict:
        """
        Execute a workflow with the given inputs.
        Returns: {"status": str, "message": str, "trace": [...]}
        """
        self.trace = []
        workflow = self.workflows.get(workflow_name)
        if not workflow:
            raise ExecutionError(f"Workflow '{workflow_name}' not found")

        self._trace("info", f"Starting workflow '{workflow_name}'")

        steps_by_name = {s.name: (i, s) for i, s in enumerate(workflow.steps)}
        current_index = 0

        while current_index < len(workflow.steps):
            step = workflow.steps[current_index]
            self._trace("info", f"→ Entering step '{step.name}'", {"step": step.name})

            # Execute policy or action
            policy_result = None
            if step.execute:
                self._trace("info", f"  Executing policy '{step.execute.policy_name}'")
                policy_result = self.evaluate_policy(step.execute.policy_name, inputs)
            elif step.action:
                self._trace("action", f"  Action: {step.action.description}", {"action": step.action.description})

            # Determine which transition to follow
            transition = self._select_transition(step, policy_result)
            if transition is None:
                raise ExecutionError(
                    f"No matching transition in step '{step.name}'"
                )

            self._trace("transition",
                         f"  Transition: on {transition.event} -> {transition.target}",
                         {"event": transition.event, "target": transition.target})

            # Follow the transition
            if transition.target == "done":
                self._trace("result", "Workflow completed successfully ✓",
                            {"status": "completed"})
                return {
                    "status": "completed",
                    "message": "Workflow completed successfully",
                    "trace": [t.to_dict() for t in self.trace],
                }
            elif transition.target == "reject":
                msg = transition.message or "Rejected"
                self._trace("result", f"Workflow rejected: {msg}",
                            {"status": "rejected", "message": msg})
                return {
                    "status": "rejected",
                    "message": msg,
                    "trace": [t.to_dict() for t in self.trace],
                }
            elif transition.target == "next":
                current_index += 1
            else:
                # Jump to named step
                if transition.target not in steps_by_name:
                    raise ExecutionError(
                        f"Unknown step target '{transition.target}'"
                    )
                current_index = steps_by_name[transition.target][0]

        self._trace("result", "Workflow completed (fell through all steps)",
                    {"status": "completed"})
        return {
            "status": "completed",
            "message": "Workflow completed (all steps executed)",
            "trace": [t.to_dict() for t in self.trace],
        }

    # ── Expression Evaluation ─────────────────────────────────────────────

    def _eval_expr(self, node: ASTNode, env: Dict[str, Any]) -> Any:
        """Recursively evaluate an expression AST node."""
        if isinstance(node, Literal):
            return node.value

        if isinstance(node, Identifier):
            if node.name not in env:
                raise ExecutionError(f"Undefined variable '{node.name}'")
            return env[node.name]

        if isinstance(node, BinaryOp):
            left = self._eval_expr(node.left, env)
            right = self._eval_expr(node.right, env)
            return self._eval_binary(node.op, left, right)

        if isinstance(node, UnaryOp):
            operand = self._eval_expr(node.operand, env)
            if node.op == "NOT":
                return not operand
            raise ExecutionError(f"Unknown unary operator '{node.op}'")

        if isinstance(node, LogicOp):
            left = self._eval_expr(node.left, env)
            right = self._eval_expr(node.right, env)
            if node.op == "AND":
                return bool(left) and bool(right)
            if node.op == "OR":
                return bool(left) or bool(right)
            raise ExecutionError(f"Unknown logic operator '{node.op}'")

        raise ExecutionError(f"Cannot evaluate node type '{type(node).__name__}'")

    def _eval_binary(self, op: str, left: Any, right: Any) -> Any:
        """Evaluate a binary operation."""
        ops = {
            "+":  lambda a, b: a + b,
            "-":  lambda a, b: a - b,
            "*":  lambda a, b: a * b,
            "/":  lambda a, b: a / b if b != 0 else (_ for _ in ()).throw(ExecutionError("Division by zero")),
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">":  lambda a, b: a > b,
            "<":  lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        if op not in ops:
            raise ExecutionError(f"Unknown operator '{op}'")

        if op == "/" and right == 0:
            raise ExecutionError("Division by zero")
        return ops[op](left, right)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _select_transition(self, step: Step, policy_result: Optional[dict]) -> Optional[Transition]:
        """Select the correct transition based on policy result or action completion."""
        for trans in step.transitions:
            if step.execute and policy_result:
                if trans.event == "pass" and policy_result["passed"]:
                    return trans
                if trans.event == "fail" and not policy_result["passed"]:
                    return trans
            elif step.action:
                if trans.event == "complete":
                    return trans
        return None

    def _coerce_input(self, value: Any, expected_type: str, name: str) -> Any:
        """Coerce an input value to the declared type."""
        try:
            if expected_type == "number":
                return float(value)
            elif expected_type == "boolean":
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes")
                return bool(value)
            elif expected_type == "string":
                return str(value)
        except (ValueError, TypeError):
            raise ExecutionError(
                f"Cannot convert input '{name}' value '{value}' to type '{expected_type}'"
            )
        return value

    def _trace(self, event_type: str, message: str, details: dict = None):
        self.trace.append(TraceEvent(event_type, message, details))
