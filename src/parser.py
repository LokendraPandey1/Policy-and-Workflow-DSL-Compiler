"""
Recursive-Descent Parser for the Policy & Workflow DSL.

Consumes a token list produced by the lexer and builds an Abstract Syntax Tree
using the node classes from ast_nodes.py.
"""

from typing import List, Optional
from src.lexer import Token, TokenType, LexerError
from src.ast_nodes import (
    Program, Policy, InputDecl, RuleDecl, EvaluateStmt,
    Workflow, Step, Transition, ExecuteStmt, ActionStmt,
    BinaryOp, UnaryOp, LogicOp, Literal, Identifier,
)


# ── Parser Errors ─────────────────────────────────────────────────────────────

class ParserError(Exception):
    def __init__(self, message: str, token: Token = None):
        self.token = token
        if token:
            loc = f" at line {token.line}, col {token.col}"
        else:
            loc = ""
        super().__init__(f"Parser error{loc}: {message}")


# ── Parser ────────────────────────────────────────────────────────────────────

class Parser:
    """
    Recursive-descent parser that transforms a token stream into an AST.

    Grammar (simplified):
        program        = (policy | workflow)+ EOF
        policy         = "policy" ID "{" (input_decl | rule_decl | evaluate_stmt)+ "}"
        input_decl     = "input" ID ":" type
        type           = "number" | "string" | "boolean"
        rule_decl      = "rule" ID ":" expression
        evaluate_stmt  = "evaluate" ":" logic_expr
        logic_expr     = logic_term ("OR" logic_term)*
        logic_term     = logic_factor ("AND" logic_factor)*
        logic_factor   = "NOT"? (comparison | ID | "(" logic_expr ")")
        comparison     = expression comp_op expression
        expression     = term (("+"|"-") term)*
        term           = factor (("*"|"/") factor)*
        factor         = NUMBER | STRING | "true" | "false" | ID | "(" expression ")"
        workflow       = "workflow" ID "{" step+ "}"
        step           = "step" ID "{" (execute_stmt | action_stmt) transition+ "}"
        execute_stmt   = "execute" "policy" ID
        action_stmt    = "action" STRING
        transition     = "on" event "->" target STRING?
        event          = "pass" | "fail" | "complete"
        target         = "next" | "done" | "reject" | ID
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    # ── Public API ────────────────────────────────────────────────────────

    def parse(self) -> Program:
        """Parse the full token stream and return a Program AST node."""
        program = Program()
        while not self._check(TokenType.EOF):
            if self._check(TokenType.POLICY):
                program.policies.append(self._parse_policy())
            elif self._check(TokenType.WORKFLOW):
                program.workflows.append(self._parse_workflow())
            else:
                raise ParserError(
                    f"Expected 'policy' or 'workflow', got '{self._current().value}'",
                    self._current(),
                )
        return program

    # ── Policy ────────────────────────────────────────────────────────────

    def _parse_policy(self) -> Policy:
        tok = self._consume(TokenType.POLICY, "Expected 'policy'")
        name_tok = self._consume(TokenType.IDENTIFIER, "Expected policy name")
        self._consume(TokenType.LBRACE, "Expected '{' after policy name")

        policy = Policy(name=name_tok.value, line=tok.line, col=tok.col)

        while not self._check(TokenType.RBRACE):
            if self._check(TokenType.INPUT):
                policy.inputs.append(self._parse_input_decl())
            elif self._check(TokenType.RULE):
                policy.rules.append(self._parse_rule_decl())
            elif self._check(TokenType.EVALUATE):
                policy.evaluate = self._parse_evaluate_stmt()
            else:
                raise ParserError(
                    f"Expected 'input', 'rule', or 'evaluate' inside policy, got '{self._current().value}'",
                    self._current(),
                )

        self._consume(TokenType.RBRACE, "Expected '}' to close policy")
        return policy

    def _parse_input_decl(self) -> InputDecl:
        tok = self._consume(TokenType.INPUT, "Expected 'input'")
        name_tok = self._consume(TokenType.IDENTIFIER, "Expected input name")
        self._consume(TokenType.COLON, "Expected ':' after input name")
        type_tok = self._consume_type("Expected type (number, string, boolean)")
        return InputDecl(name=name_tok.value, type=type_tok.value, line=tok.line, col=tok.col)

    def _parse_rule_decl(self) -> RuleDecl:
        tok = self._consume(TokenType.RULE, "Expected 'rule'")
        name_tok = self._consume(TokenType.IDENTIFIER, "Expected rule name")
        self._consume(TokenType.COLON, "Expected ':' after rule name")
        expr = self._parse_logic_expr()
        return RuleDecl(name=name_tok.value, expression=expr, line=tok.line, col=tok.col)

    def _parse_evaluate_stmt(self) -> EvaluateStmt:
        tok = self._consume(TokenType.EVALUATE, "Expected 'evaluate'")
        self._consume(TokenType.COLON, "Expected ':' after 'evaluate'")
        expr = self._parse_logic_expr()
        return EvaluateStmt(expression=expr, line=tok.line, col=tok.col)

    # ── Logic Expressions ─────────────────────────────────────────────────

    def _parse_logic_expr(self):
        """logic_expr = logic_term ('OR' logic_term)*"""
        left = self._parse_logic_term()
        while self._check(TokenType.OR):
            op_tok = self._advance()
            right = self._parse_logic_term()
            left = LogicOp(op="OR", left=left, right=right, line=op_tok.line, col=op_tok.col)
        return left

    def _parse_logic_term(self):
        """logic_term = logic_factor ('AND' logic_factor)*"""
        left = self._parse_logic_factor()
        while self._check(TokenType.AND):
            op_tok = self._advance()
            right = self._parse_logic_factor()
            left = LogicOp(op="AND", left=left, right=right, line=op_tok.line, col=op_tok.col)
        return left

    def _parse_logic_factor(self):
        """logic_factor = 'NOT'? (comparison | ID | '(' logic_expr ')')"""
        if self._check(TokenType.NOT):
            op_tok = self._advance()
            operand = self._parse_logic_factor()
            return UnaryOp(op="NOT", operand=operand, line=op_tok.line, col=op_tok.col)

        if self._check(TokenType.LPAREN):
            self._advance()
            expr = self._parse_logic_expr()
            self._consume(TokenType.RPAREN, "Expected ')' after expression")
            return expr

        # Could be a comparison (expr comp_op expr) or a bare identifier
        return self._parse_comparison_or_value()

    def _parse_comparison_or_value(self):
        """
        Try to parse a comparison.  A comparison is:
            expression comp_op expression
        If there is no comparison operator after the first expression,
        just return that expression (which may be an identifier).
        """
        left = self._parse_expression()
        if self._check_any(TokenType.EQ, TokenType.NEQ, TokenType.GT, TokenType.LT, TokenType.GTE, TokenType.LTE):
            op_tok = self._advance()
            right = self._parse_expression()
            return BinaryOp(op=op_tok.value, left=left, right=right, line=op_tok.line, col=op_tok.col)
        return left

    # ── Arithmetic Expressions ────────────────────────────────────────────

    def _parse_expression(self):
        """expression = term (('+' | '-') term)*"""
        left = self._parse_term()
        while self._check_any(TokenType.PLUS, TokenType.MINUS):
            op_tok = self._advance()
            right = self._parse_term()
            left = BinaryOp(op=op_tok.value, left=left, right=right, line=op_tok.line, col=op_tok.col)
        return left

    def _parse_term(self):
        """term = factor (('*' | '/') factor)*"""
        left = self._parse_factor()
        while self._check_any(TokenType.STAR, TokenType.SLASH):
            op_tok = self._advance()
            right = self._parse_factor()
            left = BinaryOp(op=op_tok.value, left=left, right=right, line=op_tok.line, col=op_tok.col)
        return left

    def _parse_factor(self):
        """factor = NUMBER | STRING | 'true' | 'false' | ID | '(' expression ')'"""
        tok = self._current()

        if self._check(TokenType.NUMBER):
            self._advance()
            return Literal(value=tok.value, type="number", line=tok.line, col=tok.col)

        if self._check(TokenType.STRING):
            self._advance()
            return Literal(value=tok.value, type="string", line=tok.line, col=tok.col)

        if self._check(TokenType.TRUE):
            self._advance()
            return Literal(value=True, type="boolean", line=tok.line, col=tok.col)

        if self._check(TokenType.FALSE):
            self._advance()
            return Literal(value=False, type="boolean", line=tok.line, col=tok.col)

        if self._check(TokenType.IDENTIFIER):
            self._advance()
            return Identifier(name=tok.value, line=tok.line, col=tok.col)

        if self._check(TokenType.LPAREN):
            self._advance()
            expr = self._parse_expression()
            self._consume(TokenType.RPAREN, "Expected ')'")
            return expr

        raise ParserError(f"Unexpected token '{tok.value}'", tok)

    # ── Workflow ──────────────────────────────────────────────────────────

    def _parse_workflow(self) -> Workflow:
        tok = self._consume(TokenType.WORKFLOW, "Expected 'workflow'")
        name_tok = self._consume(TokenType.IDENTIFIER, "Expected workflow name")
        self._consume(TokenType.LBRACE, "Expected '{' after workflow name")

        wf = Workflow(name=name_tok.value, line=tok.line, col=tok.col)
        while not self._check(TokenType.RBRACE):
            wf.steps.append(self._parse_step())

        self._consume(TokenType.RBRACE, "Expected '}' to close workflow")
        return wf

    def _parse_step(self) -> Step:
        tok = self._consume(TokenType.STEP, "Expected 'step'")
        name_tok = self._consume(TokenType.IDENTIFIER, "Expected step name")
        self._consume(TokenType.LBRACE, "Expected '{' after step name")

        step = Step(name=name_tok.value, line=tok.line, col=tok.col)

        # Execute or Action
        if self._check(TokenType.EXECUTE):
            step.execute = self._parse_execute_stmt()
        elif self._check(TokenType.ACTION):
            step.action = self._parse_action_stmt()
        else:
            raise ParserError(
                f"Expected 'execute' or 'action' inside step, got '{self._current().value}'",
                self._current(),
            )

        # At least one transition
        if not self._check(TokenType.ON):
            raise ParserError("Expected at least one 'on' transition in step", self._current())
        while self._check(TokenType.ON):
            step.transitions.append(self._parse_transition())

        self._consume(TokenType.RBRACE, "Expected '}' to close step")
        return step

    def _parse_execute_stmt(self) -> ExecuteStmt:
        tok = self._consume(TokenType.EXECUTE, "Expected 'execute'")
        self._consume(TokenType.POLICY, "Expected 'policy' after 'execute'")
        name_tok = self._consume(TokenType.IDENTIFIER, "Expected policy name")
        return ExecuteStmt(policy_name=name_tok.value, line=tok.line, col=tok.col)

    def _parse_action_stmt(self) -> ActionStmt:
        tok = self._consume(TokenType.ACTION, "Expected 'action'")
        desc_tok = self._consume(TokenType.STRING, "Expected string after 'action'")
        return ActionStmt(description=desc_tok.value, line=tok.line, col=tok.col)

    def _parse_transition(self) -> Transition:
        tok = self._consume(TokenType.ON, "Expected 'on'")

        # Event: pass | fail | complete
        event_tok = self._current()
        if event_tok.type in (TokenType.PASS, TokenType.FAIL, TokenType.COMPLETE):
            self._advance()
        else:
            raise ParserError(
                f"Expected 'pass', 'fail', or 'complete', got '{event_tok.value}'",
                event_tok,
            )

        self._consume(TokenType.ARROW, "Expected '->' after event")

        # Target: next | done | reject | ID
        target_tok = self._current()
        if target_tok.type in (TokenType.NEXT, TokenType.DONE, TokenType.REJECT, TokenType.IDENTIFIER):
            self._advance()
        else:
            raise ParserError(
                f"Expected 'next', 'done', 'reject', or step name, got '{target_tok.value}'",
                target_tok,
            )

        # Optional message string (commonly used with reject)
        message = ""
        if self._check(TokenType.STRING):
            message = self._advance().value

        return Transition(
            event=event_tok.value, target=target_tok.value,
            message=message, line=tok.line, col=tok.col,
        )

    # ── Token Navigation Helpers ──────────────────────────────────────────

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _check(self, token_type: TokenType) -> bool:
        return self.tokens[self.pos].type == token_type

    def _check_any(self, *types: TokenType) -> bool:
        return self.tokens[self.pos].type in types

    def _consume(self, token_type: TokenType, error_msg: str) -> Token:
        if self._check(token_type):
            return self._advance()
        raise ParserError(error_msg, self._current())

    def _consume_type(self, error_msg: str) -> Token:
        """Consume a type keyword: number | string | boolean."""
        if self._check_any(TokenType.TYPE_NUMBER, TokenType.TYPE_STRING, TokenType.TYPE_BOOLEAN):
            return self._advance()
        raise ParserError(error_msg, self._current())


def parse(tokens: List[Token]) -> Program:
    """Convenience function: parse a token list and return the AST."""
    return Parser(tokens).parse()
