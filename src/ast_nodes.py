"""
AST Node Definitions for the Policy & Workflow DSL.

Each node is a dataclass representing a construct in the language.
Every node has a `to_dict()` method for JSON serialization (used by the visualizer).
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ── Base ──────────────────────────────────────────────────────────────────────

@dataclass
class ASTNode:
    """Base class for all AST nodes."""
    line: int = 0
    col: int = 0

    def to_dict(self) -> dict:
        raise NotImplementedError


# ── Expressions ───────────────────────────────────────────────────────────────

@dataclass
class Literal(ASTNode):
    """A literal value: number, string, or boolean."""
    value: object = None
    type: str = ""  # "number", "string", "boolean"

    def to_dict(self):
        return {"node": "Literal", "value": self.value, "type": self.type}


@dataclass
class Identifier(ASTNode):
    """A reference to a named variable or rule."""
    name: str = ""

    def to_dict(self):
        return {"node": "Identifier", "name": self.name}


@dataclass
class BinaryOp(ASTNode):
    """A binary operation: arithmetic (+, -, *, /) or comparison (==, !=, >, <, >=, <=)."""
    op: str = ""
    left: ASTNode = None
    right: ASTNode = None

    def to_dict(self):
        return {
            "node": "BinaryOp",
            "op": self.op,
            "left": self.left.to_dict() if self.left else None,
            "right": self.right.to_dict() if self.right else None,
        }


@dataclass
class UnaryOp(ASTNode):
    """A unary operation: NOT."""
    op: str = ""
    operand: ASTNode = None

    def to_dict(self):
        return {
            "node": "UnaryOp",
            "op": self.op,
            "operand": self.operand.to_dict() if self.operand else None,
        }


@dataclass
class LogicOp(ASTNode):
    """A logical operation: AND / OR."""
    op: str = ""
    left: ASTNode = None
    right: ASTNode = None

    def to_dict(self):
        return {
            "node": "LogicOp",
            "op": self.op,
            "left": self.left.to_dict() if self.left else None,
            "right": self.right.to_dict() if self.right else None,
        }


# ── Policy Nodes ──────────────────────────────────────────────────────────────

@dataclass
class InputDecl(ASTNode):
    """An input declaration inside a policy: `input gpa: number`."""
    name: str = ""
    type: str = ""  # "number", "string", "boolean"

    def to_dict(self):
        return {"node": "InputDecl", "name": self.name, "type": self.type}


@dataclass
class RuleDecl(ASTNode):
    """A named rule inside a policy: `rule min_gpa: gpa >= 3.0`."""
    name: str = ""
    expression: ASTNode = None

    def to_dict(self):
        return {
            "node": "RuleDecl",
            "name": self.name,
            "expression": self.expression.to_dict() if self.expression else None,
        }


@dataclass
class EvaluateStmt(ASTNode):
    """The evaluate statement: `evaluate: min_gpa AND min_credits AND active`."""
    expression: ASTNode = None

    def to_dict(self):
        return {
            "node": "EvaluateStmt",
            "expression": self.expression.to_dict() if self.expression else None,
        }


@dataclass
class Policy(ASTNode):
    """A policy block containing inputs, rules, and an evaluate statement."""
    name: str = ""
    inputs: List[InputDecl] = field(default_factory=list)
    rules: List[RuleDecl] = field(default_factory=list)
    evaluate: EvaluateStmt = None

    def to_dict(self):
        return {
            "node": "Policy",
            "name": self.name,
            "inputs": [i.to_dict() for i in self.inputs],
            "rules": [r.to_dict() for r in self.rules],
            "evaluate": self.evaluate.to_dict() if self.evaluate else None,
        }


# ── Workflow Nodes ────────────────────────────────────────────────────────────

@dataclass
class Transition(ASTNode):
    """A transition within a step: `on pass -> next` or `on fail -> reject "msg"`."""
    event: str = ""      # "pass", "fail", "complete"
    target: str = ""     # "next", "done", "reject", or a step name
    message: str = ""    # optional message for reject

    def to_dict(self):
        d = {"node": "Transition", "event": self.event, "target": self.target}
        if self.message:
            d["message"] = self.message
        return d


@dataclass
class ExecuteStmt(ASTNode):
    """An execute statement inside a step: `execute policy StudentEligibility`."""
    policy_name: str = ""

    def to_dict(self):
        return {"node": "ExecuteStmt", "policy_name": self.policy_name}


@dataclass
class ActionStmt(ASTNode):
    """An action statement inside a step: `action "Send email"`."""
    description: str = ""

    def to_dict(self):
        return {"node": "ActionStmt", "description": self.description}


@dataclass
class Step(ASTNode):
    """A workflow step containing an execute/action and transitions."""
    name: str = ""
    execute: ExecuteStmt = None
    action: ActionStmt = None
    transitions: List[Transition] = field(default_factory=list)

    def to_dict(self):
        d = {"node": "Step", "name": self.name, "transitions": [t.to_dict() for t in self.transitions]}
        if self.execute:
            d["execute"] = self.execute.to_dict()
        if self.action:
            d["action"] = self.action.to_dict()
        return d


@dataclass
class Workflow(ASTNode):
    """A workflow block containing ordered steps."""
    name: str = ""
    steps: List[Step] = field(default_factory=list)

    def to_dict(self):
        return {
            "node": "Workflow",
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
        }


# ── Top-Level ─────────────────────────────────────────────────────────────────

@dataclass
class Program(ASTNode):
    """The root node of the AST: a collection of policies and workflows."""
    policies: List[Policy] = field(default_factory=list)
    workflows: List[Workflow] = field(default_factory=list)

    def to_dict(self):
        return {
            "node": "Program",
            "policies": [p.to_dict() for p in self.policies],
            "workflows": [w.to_dict() for w in self.workflows],
        }
