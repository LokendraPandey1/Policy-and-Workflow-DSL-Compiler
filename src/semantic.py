"""
Semantic Analyzer for the Policy & Workflow DSL.

Performs static validation on the AST, catching errors such as:
  - Duplicate policy, workflow, input, or rule names
  - Undefined identifier references in rules / evaluate expressions
  - Undefined policy references in workflow execute statements
  - Workflow step transition targets that don't exist
  - Basic type checking in comparisons
"""

from typing import List, Dict, Set, Optional
from src.ast_nodes import (
    Program, Policy, InputDecl, RuleDecl, EvaluateStmt,
    Workflow, Step, Transition, ExecuteStmt, ActionStmt,
    BinaryOp, UnaryOp, LogicOp, Literal, Identifier, ASTNode,
)


# ── Semantic Error ────────────────────────────────────────────────────────────

class SemanticError:
    """A single semantic error with location information."""
    def __init__(self, message: str, line: int = 0, col: int = 0):
        self.message = message
        self.line = line
        self.col = col

    def to_dict(self):
        return {"message": self.message, "line": self.line, "col": self.col}

    def __str__(self):
        return f"Semantic error at line {self.line}, col {self.col}: {self.message}"


# ── Symbol Table ──────────────────────────────────────────────────────────────

class SymbolTable:
    """Tracks declared symbols across scopes for validation."""

    def __init__(self):
        self.policies: Dict[str, Policy] = {}
        self.workflows: Dict[str, Workflow] = {}
        # Per-policy scope
        self.current_inputs: Dict[str, str] = {}   # name -> type
        self.current_rules: Dict[str, RuleDecl] = {}  # name -> node
        # Per-workflow scope
        self.current_steps: Dict[str, Step] = {}    # name -> node

    def enter_policy(self):
        self.current_inputs.clear()
        self.current_rules.clear()

    def enter_workflow(self):
        self.current_steps.clear()


# ── Analyzer ──────────────────────────────────────────────────────────────────

class SemanticAnalyzer:
    """Validates the AST and returns a list of SemanticError objects."""

    def __init__(self):
        self.errors: List[SemanticError] = []
        self.symbols = SymbolTable()

    def analyze(self, program: Program) -> List[SemanticError]:
        """Run all semantic checks and return a list of errors (empty = valid)."""
        self.errors = []
        self.symbols = SymbolTable()

        # First pass: register all top-level names
        for policy in program.policies:
            if policy.name in self.symbols.policies:
                self._error(f"Duplicate policy name '{policy.name}'", policy)
            else:
                self.symbols.policies[policy.name] = policy

        for workflow in program.workflows:
            if workflow.name in self.symbols.workflows:
                self._error(f"Duplicate workflow name '{workflow.name}'", workflow)
            else:
                self.symbols.workflows[workflow.name] = workflow

        # Second pass: validate internals
        for policy in program.policies:
            self._analyze_policy(policy)
        for workflow in program.workflows:
            self._analyze_workflow(workflow)

        return self.errors

    # ── Policy Validation ─────────────────────────────────────────────────

    def _analyze_policy(self, policy: Policy):
        self.symbols.enter_policy()

        # Register inputs
        for inp in policy.inputs:
            if inp.name in self.symbols.current_inputs:
                self._error(f"Duplicate input '{inp.name}' in policy '{policy.name}'", inp)
            else:
                self.symbols.current_inputs[inp.name] = inp.type

        # Register and validate rules
        for rule in policy.rules:
            if rule.name in self.symbols.current_rules:
                self._error(f"Duplicate rule '{rule.name}' in policy '{policy.name}'", rule)
            else:
                self.symbols.current_rules[rule.name] = rule
            self._check_expression(rule.expression, policy.name)

        # Validate evaluate statement
        if policy.evaluate:
            self._check_evaluate_expr(policy.evaluate.expression, policy.name)
        else:
            self._error(f"Policy '{policy.name}' is missing an 'evaluate' statement", policy)

    def _check_expression(self, node: ASTNode, policy_name: str):
        """Check that all identifiers in an expression are declared inputs."""
        if node is None:
            return
        if isinstance(node, Identifier):
            if node.name not in self.symbols.current_inputs:
                self._error(
                    f"Undefined input '{node.name}' in policy '{policy_name}'",
                    node,
                )
        elif isinstance(node, BinaryOp):
            self._check_expression(node.left, policy_name)
            self._check_expression(node.right, policy_name)
            self._check_comparison_types(node, policy_name)
        elif isinstance(node, UnaryOp):
            self._check_expression(node.operand, policy_name)
        elif isinstance(node, LogicOp):
            self._check_expression(node.left, policy_name)
            self._check_expression(node.right, policy_name)

    def _check_evaluate_expr(self, node: ASTNode, policy_name: str):
        """Check that evaluate expression references only declared rules or valid sub-expressions."""
        if node is None:
            return
        if isinstance(node, Identifier):
            # In evaluate, identifiers should be rule names
            if (node.name not in self.symbols.current_rules and
                    node.name not in self.symbols.current_inputs):
                self._error(
                    f"Undefined reference '{node.name}' in evaluate of policy '{policy_name}'",
                    node,
                )
        elif isinstance(node, LogicOp):
            self._check_evaluate_expr(node.left, policy_name)
            self._check_evaluate_expr(node.right, policy_name)
        elif isinstance(node, UnaryOp):
            self._check_evaluate_expr(node.operand, policy_name)
        elif isinstance(node, BinaryOp):
            self._check_expression(node.left, policy_name)
            self._check_expression(node.right, policy_name)

    def _check_comparison_types(self, node: BinaryOp, policy_name: str):
        """Warn if comparing obviously incompatible types."""
        if node.op not in ("==", "!=", ">", "<", ">=", "<="):
            return
        left_type = self._infer_type(node.left)
        right_type = self._infer_type(node.right)
        if left_type and right_type and left_type != right_type:
            self._error(
                f"Type mismatch in comparison: '{left_type}' {node.op} '{right_type}' "
                f"in policy '{policy_name}'",
                node,
            )

    def _infer_type(self, node: ASTNode) -> Optional[str]:
        """Try to infer the type of an expression node."""
        if isinstance(node, Literal):
            return node.type
        if isinstance(node, Identifier):
            return self.symbols.current_inputs.get(node.name)
        return None

    # ── Workflow Validation ───────────────────────────────────────────────

    def _analyze_workflow(self, workflow: Workflow):
        self.symbols.enter_workflow()

        # Register steps
        for step in workflow.steps:
            if step.name in self.symbols.current_steps:
                self._error(
                    f"Duplicate step '{step.name}' in workflow '{workflow.name}'",
                    step,
                )
            else:
                self.symbols.current_steps[step.name] = step

        # Validate each step
        for i, step in enumerate(workflow.steps):
            # Validate execute references
            if step.execute:
                if step.execute.policy_name not in self.symbols.policies:
                    self._error(
                        f"Undefined policy '{step.execute.policy_name}' "
                        f"in step '{step.name}' of workflow '{workflow.name}'",
                        step.execute,
                    )

            # Validate transitions
            for trans in step.transitions:
                if trans.target not in ("next", "done", "reject"):
                    # Must be a valid step name
                    if trans.target not in self.symbols.current_steps:
                        self._error(
                            f"Undefined step target '{trans.target}' "
                            f"in step '{step.name}' of workflow '{workflow.name}'",
                            trans,
                        )

                # Validate 'next' isn't used on the last step
                if trans.target == "next" and i == len(workflow.steps) - 1:
                    self._error(
                        f"Transition 'next' on the last step '{step.name}' "
                        f"in workflow '{workflow.name}' has no following step",
                        trans,
                    )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _error(self, message: str, node: ASTNode):
        self.errors.append(SemanticError(message, node.line, node.col))


def analyze(program: Program) -> List[SemanticError]:
    """Convenience function: run semantic analysis and return errors."""
    return SemanticAnalyzer().analyze(program)
