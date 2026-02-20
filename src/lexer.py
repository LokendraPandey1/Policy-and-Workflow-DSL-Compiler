"""
Lexer (Tokenizer) for the Policy & Workflow DSL.

Converts raw source text into a flat list of Token objects, each carrying:
  - type   : a TokenType enum value
  - value  : the matched string (or converted Python value for literals)
  - line   : 1-based source line
  - col    : 1-based source column
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List
import re


# ── Token Types ───────────────────────────────────────────────────────────────

class TokenType(Enum):
    # Keywords
    POLICY = auto()
    WORKFLOW = auto()
    STEP = auto()
    RULE = auto()
    INPUT = auto()
    EVALUATE = auto()
    EXECUTE = auto()
    ACTION = auto()
    ON = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    TRUE = auto()
    FALSE = auto()
    PASS = auto()
    FAIL = auto()
    COMPLETE = auto()
    NEXT = auto()
    DONE = auto()
    REJECT = auto()

    # Type keywords
    TYPE_NUMBER = auto()
    TYPE_STRING = auto()
    TYPE_BOOLEAN = auto()

    # Literals
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    EQ = auto()         # ==
    NEQ = auto()        # !=
    GT = auto()         # >
    LT = auto()         # <
    GTE = auto()        # >=
    LTE = auto()        # <=

    # Delimiters
    LBRACE = auto()     # {
    RBRACE = auto()     # }
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    COLON = auto()      # :
    ARROW = auto()      # ->
    COMMA = auto()      # ,

    # Special
    EOF = auto()


# ── Keyword Map ───────────────────────────────────────────────────────────────

KEYWORDS = {
    "policy":   TokenType.POLICY,
    "workflow":  TokenType.WORKFLOW,
    "step":     TokenType.STEP,
    "rule":     TokenType.RULE,
    "input":    TokenType.INPUT,
    "evaluate": TokenType.EVALUATE,
    "execute":  TokenType.EXECUTE,
    "action":   TokenType.ACTION,
    "on":       TokenType.ON,
    "AND":      TokenType.AND,
    "OR":       TokenType.OR,
    "NOT":      TokenType.NOT,
    "true":     TokenType.TRUE,
    "false":    TokenType.FALSE,
    "pass":     TokenType.PASS,
    "fail":     TokenType.FAIL,
    "complete": TokenType.COMPLETE,
    "next":     TokenType.NEXT,
    "done":     TokenType.DONE,
    "reject":   TokenType.REJECT,
    "number":   TokenType.TYPE_NUMBER,
    "string":   TokenType.TYPE_STRING,
    "boolean":  TokenType.TYPE_BOOLEAN,
}


# ── Token ─────────────────────────────────────────────────────────────────────

@dataclass
class Token:
    type: TokenType
    value: object
    line: int
    col: int

    def to_dict(self):
        return {
            "type": self.type.name,
            "value": self.value if not isinstance(self.value, float) or self.value != int(self.value)
                     else int(self.value),
            "line": self.line,
            "col": self.col,
        }


# ── Lexer Errors ──────────────────────────────────────────────────────────────

class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int):
        self.line = line
        self.col = col
        super().__init__(f"Lexer error at line {line}, col {col}: {message}")


# ── Lexer ─────────────────────────────────────────────────────────────────────

class Lexer:
    """Tokenizes DSL source code into a list of Token objects."""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    # -- Public API --

    def tokenize(self) -> List[Token]:
        """Scan the entire source and return a list of tokens (including EOF)."""
        while self.pos < len(self.source):
            self._skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break

            ch = self.source[self.pos]

            # String literal
            if ch == '"':
                self._read_string()
            # Number literal
            elif ch.isdigit():
                self._read_number()
            # Identifier or keyword
            elif ch.isalpha() or ch == '_':
                self._read_identifier()
            # Two-character operators
            elif self._match("->"):
                self._add(TokenType.ARROW, "->", 2)
            elif self._match(">="):
                self._add(TokenType.GTE, ">=", 2)
            elif self._match("<="):
                self._add(TokenType.LTE, "<=", 2)
            elif self._match("=="):
                self._add(TokenType.EQ, "==", 2)
            elif self._match("!="):
                self._add(TokenType.NEQ, "!=", 2)
            # Single-character operators / delimiters
            elif ch == '>':
                self._add(TokenType.GT, ">")
            elif ch == '<':
                self._add(TokenType.LT, "<")
            elif ch == '+':
                self._add(TokenType.PLUS, "+")
            elif ch == '-':
                self._add(TokenType.MINUS, "-")
            elif ch == '*':
                self._add(TokenType.STAR, "*")
            elif ch == '/':
                self._add(TokenType.SLASH, "/")
            elif ch == '{':
                self._add(TokenType.LBRACE, "{")
            elif ch == '}':
                self._add(TokenType.RBRACE, "}")
            elif ch == '(':
                self._add(TokenType.LPAREN, "(")
            elif ch == ')':
                self._add(TokenType.RPAREN, ")")
            elif ch == ':':
                self._add(TokenType.COLON, ":")
            elif ch == ',':
                self._add(TokenType.COMMA, ",")
            else:
                raise LexerError(f"Unexpected character '{ch}'", self.line, self.col)

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.col))
        return self.tokens

    # -- Helpers --

    def _skip_whitespace_and_comments(self):
        """Skip spaces, tabs, newlines, and // line comments."""
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == '\n':
                self.pos += 1
                self.line += 1
                self.col = 1
            elif ch in (' ', '\t', '\r'):
                self.pos += 1
                self.col += 1
            elif ch == '/' and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == '/':
                # Skip comment until end of line
                while self.pos < len(self.source) and self.source[self.pos] != '\n':
                    self.pos += 1
            else:
                break

    def _match(self, expected: str) -> bool:
        """Check if the source starting at pos matches the expected string."""
        return self.source[self.pos:self.pos + len(expected)] == expected

    def _add(self, token_type: TokenType, value: object, length: int = 1):
        """Add a token and advance position."""
        self.tokens.append(Token(token_type, value, self.line, self.col))
        self.pos += length
        self.col += length

    def _read_string(self):
        """Read a string literal enclosed in double quotes."""
        start_line, start_col = self.line, self.col
        self.pos += 1  # skip opening "
        self.col += 1
        result = []
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch == '"':
                self.pos += 1
                self.col += 1
                self.tokens.append(Token(TokenType.STRING, ''.join(result), start_line, start_col))
                return
            if ch == '\n':
                raise LexerError("Unterminated string literal", start_line, start_col)
            if ch == '\\' and self.pos + 1 < len(self.source):
                next_ch = self.source[self.pos + 1]
                escape_map = {'n': '\n', 't': '\t', '\\': '\\', '"': '"'}
                if next_ch in escape_map:
                    result.append(escape_map[next_ch])
                    self.pos += 2
                    self.col += 2
                    continue
            result.append(ch)
            self.pos += 1
            self.col += 1
        raise LexerError("Unterminated string literal", start_line, start_col)

    def _read_number(self):
        """Read an integer or decimal number."""
        start_col = self.col
        start_pos = self.pos
        has_dot = False
        while self.pos < len(self.source) and (self.source[self.pos].isdigit() or self.source[self.pos] == '.'):
            if self.source[self.pos] == '.':
                if has_dot:
                    break
                has_dot = True
            self.pos += 1
            self.col += 1
        value = float(self.source[start_pos:self.pos])
        self.tokens.append(Token(TokenType.NUMBER, value, self.line, start_col))

    def _read_identifier(self):
        """Read an identifier or keyword."""
        start_col = self.col
        start_pos = self.pos
        while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == '_'):
            self.pos += 1
            self.col += 1
        word = self.source[start_pos:self.pos]
        token_type = KEYWORDS.get(word, TokenType.IDENTIFIER)
        self.tokens.append(Token(token_type, word, self.line, start_col))


def tokenize(source: str) -> List[Token]:
    """Convenience function: tokenize source code and return the token list."""
    return Lexer(source).tokenize()
