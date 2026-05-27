"""
Python Code Generator for the Policy & Workflow DSL.

Traverses the AST and produces equivalent, runnable Python source code.
  - Policies  → Python functions returning True/False
  - Workflows → Python functions calling policy functions and printing actions
"""

from src.ast_nodes import (
    Program, Policy, InputDecl, RuleDecl, EvaluateStmt,
    Workflow, Step, Transition, ExecuteStmt, ActionStmt,
    BinaryOp, UnaryOp, LogicOp, Literal, Identifier, ASTNode,
)


class CodeGenerator:
    """Generates Python source code from the DSL AST."""

    def __init__(self):
        self._indent = 0
        self._lines = []

    def generate(self, program: Program) -> str:
        """Generate complete Python source from the Program AST."""
        self._lines = []
        self._indent = 0

        self._emit("# ── Auto-generated Python code from Policy & Workflow DSL ──")
        self._emit("")

        # Generate ALL policies first
        for policy in program.policies:
            self._gen_policy(policy)
            self._emit("")

        # Then generate ALL workflows
        for workflow in program.workflows:
            self._gen_workflow(workflow, program)
            self._emit("")

        # Generate a main block that runs each workflow
        if program.workflows:
            self._emit("")
            self._emit('if __name__ == "__main__":')
            self._indent += 1
            for wf in program.workflows:
                policy_names = set()
                for step in wf.steps:
                    if step.execute:
                        policy_names.add(step.execute.policy_name)
                # Collect all inputs from referenced policies
                all_inputs = {}
                for pname in policy_names:
                    for p in program.policies:
                        if p.name == pname:
                            for inp in p.inputs:
                                all_inputs[inp.name] = inp.type
                # Build sample inputs
                sample_vals = []
                for name, typ in all_inputs.items():
                    if typ == "number":
                        sample_vals.append(f'"{name}": 0')
                    elif typ == "boolean":
                        sample_vals.append(f'"{name}": True')
                    else:
                        sample_vals.append(f'"{name}": ""')
                inputs_str = ", ".join(sample_vals)
                self._emit(f"# Run {wf.name}")
                self._emit(f"sample_inputs = {{{inputs_str}}}")
                self._emit(f"result = {self._func_name(wf.name)}(sample_inputs)")
                self._emit(f'print(f"Workflow {wf.name}: {{result}}")')
            self._indent -= 1

        return "\n".join(self._lines)

    # ── Policy Generation ─────────────────────────────────────────────────

    def _gen_policy(self, policy: Policy):
        self._emit(f"def {self._func_name(policy.name)}(inputs):")
        self._indent += 1
        self._emit(f'"""Policy: {policy.name}"""')

        # Extract inputs
        for inp in policy.inputs:
            self._emit(f'{inp.name} = inputs["{inp.name}"]')

        self._emit("")

        # Evaluate rules
        self._emit("# Rules")
        for rule in policy.rules:
            expr_str = self._expr_to_python(rule.expression)
            self._emit(f"rule_{rule.name} = {expr_str}")

        self._emit("")

        # Final evaluation
        eval_str = self._eval_to_python(policy.evaluate.expression)
        self._emit(f"# Evaluate")
        self._emit(f"result = {eval_str}")
        self._emit("")

        # Return result with details
        rule_dict_items = ", ".join(
            f'"{r.name}": rule_{r.name}' for r in policy.rules
        )
        self._emit(f"return {{")
        self._indent += 1
        self._emit(f'"passed": result,')
        self._emit(f'"rules": {{{rule_dict_items}}}')
        self._indent -= 1
        self._emit(f"}}")

        self._indent -= 1

    # ── Workflow Generation ───────────────────────────────────────────────

    def _gen_workflow(self, workflow: Workflow, program: Program):
        self._emit(f"def {self._func_name(workflow.name)}(inputs):")
        self._indent += 1
        self._emit(f'"""Workflow: {workflow.name}"""')
        self._emit(f'print("Starting workflow: {workflow.name}")')
        self._emit("")

        for i, step in enumerate(workflow.steps):
            self._emit(f"# Step: {step.name}")
            self._emit(f'print("  → Step: {step.name}")')

            if step.execute:
                self._emit(f"policy_result = {self._func_name(step.execute.policy_name)}(inputs)")
                # Generate transitions based on policy result
                for j, trans in enumerate(step.transitions):
                    prefix = "if" if j == 0 else "elif"
                    if trans.event == "pass":
                        self._emit(f'{prefix} policy_result["passed"]:')
                    elif trans.event == "fail":
                        self._emit(f'{prefix} not policy_result["passed"]:')
                    else:
                        self._emit(f"{prefix} True:")
                    self._indent += 1
                    self._gen_transition_body(trans, workflow, i)
                    self._indent -= 1
            elif step.action:
                self._emit(f'print("    Action: {step.action.description}")')
                for trans in step.transitions:
                    if trans.event == "complete":
                        self._gen_transition_body(trans, workflow, i)
            self._emit("")

        self._emit('return {"status": "completed", "message": "Workflow completed"}')
        self._indent -= 1

    def _gen_transition_body(self, trans: Transition, workflow: Workflow, step_index: int):
        if trans.target == "done":
            self._emit(f'print("  ✓ Workflow completed")')
            self._emit(f'return {{"status": "completed", "message": "Workflow completed"}}')
        elif trans.target == "reject":
            msg = trans.message or "Rejected"
            self._emit(f'print("  ✗ Rejected: {msg}")')
            self._emit(f'return {{"status": "rejected", "message": "{msg}"}}')
        elif trans.target == "next":
            self._emit(f'print("    → Moving to next step")')
        else:
            self._emit(f'print("    → Jumping to step {trans.target}")')
            # Note: In generated code, goto-like jumps are complex. We add a comment.
            self._emit(f"# Jump to step: {trans.target}")

    # ── Expression to Python ──────────────────────────────────────────────

    def _expr_to_python(self, node: ASTNode) -> str:
        """Convert an expression AST node to a Python expression string."""
        if isinstance(node, Literal):
            if node.type == "string":
                return f'"{node.value}"'
            if node.type == "boolean":
                return "True" if node.value else "False"
            val = node.value
            if isinstance(val, float) and val == int(val):
                return str(int(val))
            return str(val)

        if isinstance(node, Identifier):
            return node.name

        if isinstance(node, BinaryOp):
            left = self._expr_to_python(node.left)
            right = self._expr_to_python(node.right)
            return f"({left} {node.op} {right})"

        if isinstance(node, UnaryOp):
            operand = self._expr_to_python(node.operand)
            if node.op == "NOT":
                return f"(not {operand})"
            return f"({node.op} {operand})"

        if isinstance(node, LogicOp):
            left = self._expr_to_python(node.left)
            right = self._expr_to_python(node.right)
            py_op = "and" if node.op == "AND" else "or"
            return f"({left} {py_op} {right})"

        return "None"

    def _eval_to_python(self, node: ASTNode) -> str:
        """Convert an evaluate expression where identifiers are rule names."""
        if isinstance(node, Identifier):
            return f"rule_{node.name}"

        if isinstance(node, LogicOp):
            left = self._eval_to_python(node.left)
            right = self._eval_to_python(node.right)
            py_op = "and" if node.op == "AND" else "or"
            return f"({left} {py_op} {right})"

        if isinstance(node, UnaryOp):
            operand = self._eval_to_python(node.operand)
            if node.op == "NOT":
                return f"(not {operand})"

        return self._expr_to_python(node)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _func_name(self, name: str) -> str:
        """Convert a PascalCase name to a snake_case function name."""
        result = []
        for i, ch in enumerate(name):
            if ch.isupper() and i > 0:
                result.append("_")
            result.append(ch.lower())
        return "".join(result)

    def _emit(self, line: str):
        prefix = "    " * self._indent
        self._lines.append(f"{prefix}{line}" if line else "")


def generate(program: Program) -> str:
    """Convenience function: generate Python code from the AST."""
    return CodeGenerator().generate(program)
