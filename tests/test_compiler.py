"""
Tests for the DSL Compiler Pipeline.

Covers: lexer, parser, semantic analysis, interpreter, and code generation.
"""

import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lexer import Lexer, TokenType, LexerError
from src.parser import Parser, ParserError
from src.semantic import SemanticAnalyzer
from src.interpreter import Interpreter, ExecutionError
from src.codegen import CodeGenerator
from src.compiler import compile_dsl


# ── Sample DSL Programs ──────────────────────────────────────────────────────

VALID_PROGRAM = """
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
"""

SIMPLE_POLICY = """
policy GradeCheck {
    input score: number
    rule passing: score >= 50
    evaluate: passing
}
"""

# ── Lexer Tests ───────────────────────────────────────────────────────────────

def test_lexer_basic_tokens():
    """Test that lexer produces correct token types for a simple policy."""
    lexer = Lexer(SIMPLE_POLICY)
    tokens = lexer.tokenize()

    types = [t.type for t in tokens]
    assert TokenType.POLICY in types
    assert TokenType.IDENTIFIER in types
    assert TokenType.INPUT in types
    assert TokenType.RULE in types
    assert TokenType.EVALUATE in types
    assert TokenType.LBRACE in types
    assert TokenType.RBRACE in types
    assert TokenType.COLON in types
    assert TokenType.GTE in types
    assert TokenType.NUMBER in types
    assert TokenType.EOF in types
    print("  ✓ test_lexer_basic_tokens passed")


def test_lexer_keywords():
    """Test that all keywords are correctly recognized."""
    source = "policy workflow step rule input evaluate execute action on AND OR NOT true false pass fail complete next done reject number string boolean"
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    expected = [
        TokenType.POLICY, TokenType.WORKFLOW, TokenType.STEP, TokenType.RULE,
        TokenType.INPUT, TokenType.EVALUATE, TokenType.EXECUTE, TokenType.ACTION,
        TokenType.ON, TokenType.AND, TokenType.OR, TokenType.NOT,
        TokenType.TRUE, TokenType.FALSE, TokenType.PASS, TokenType.FAIL,
        TokenType.COMPLETE, TokenType.NEXT, TokenType.DONE, TokenType.REJECT,
        TokenType.TYPE_NUMBER, TokenType.TYPE_STRING, TokenType.TYPE_BOOLEAN,
        TokenType.EOF,
    ]
    actual = [t.type for t in tokens]
    assert actual == expected, f"Expected {expected}, got {actual}"
    print("  ✓ test_lexer_keywords passed")


def test_lexer_operators():
    """Test that all operators are recognized."""
    source = '+ - * / == != > < >= <= -> :'
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    expected = [
        TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
        TokenType.EQ, TokenType.NEQ, TokenType.GT, TokenType.LT,
        TokenType.GTE, TokenType.LTE, TokenType.ARROW, TokenType.COLON,
        TokenType.EOF,
    ]
    actual = [t.type for t in tokens]
    assert actual == expected, f"Expected {expected}, got {actual}"
    print("  ✓ test_lexer_operators passed")


def test_lexer_string_literal():
    """Test string literal tokenization."""
    lexer = Lexer('"Hello World"')
    tokens = lexer.tokenize()
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == "Hello World"
    print("  ✓ test_lexer_string_literal passed")


def test_lexer_number_literal():
    """Test number literal tokenization."""
    lexer = Lexer('42 3.14')
    tokens = lexer.tokenize()
    assert tokens[0].type == TokenType.NUMBER
    assert tokens[0].value == 42.0
    assert tokens[1].type == TokenType.NUMBER
    assert tokens[1].value == 3.14
    print("  ✓ test_lexer_number_literal passed")


def test_lexer_line_tracking():
    """Test that line numbers are tracked correctly."""
    source = "policy\nMyPolicy\n{"
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    assert tokens[0].line == 1  # policy
    assert tokens[1].line == 2  # MyPolicy
    assert tokens[2].line == 3  # {
    print("  ✓ test_lexer_line_tracking passed")


def test_lexer_comments():
    """Test that // comments are skipped."""
    source = "// This is a comment\npolicy"
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    assert tokens[0].type == TokenType.POLICY
    print("  ✓ test_lexer_comments passed")


def test_lexer_error():
    """Test that unexpected characters raise errors."""
    try:
        Lexer('@').tokenize()
        assert False, "Should have raised LexerError"
    except LexerError as e:
        assert "Unexpected character" in str(e)
    print("  ✓ test_lexer_error passed")


# ── Parser Tests ──────────────────────────────────────────────────────────────

def test_parser_simple_policy():
    """Test parsing a simple policy into an AST."""
    tokens = Lexer(SIMPLE_POLICY).tokenize()
    ast = Parser(tokens).parse()
    assert len(ast.policies) == 1
    policy = ast.policies[0]
    assert policy.name == "GradeCheck"
    assert len(policy.inputs) == 1
    assert policy.inputs[0].name == "score"
    assert policy.inputs[0].type == "number"
    assert len(policy.rules) == 1
    assert policy.rules[0].name == "passing"
    assert policy.evaluate is not None
    print("  ✓ test_parser_simple_policy passed")


def test_parser_full_program():
    """Test parsing a full program with policy and workflow."""
    tokens = Lexer(VALID_PROGRAM).tokenize()
    ast = Parser(tokens).parse()
    assert len(ast.policies) == 1
    assert len(ast.workflows) == 1
    wf = ast.workflows[0]
    assert wf.name == "EnrollmentProcess"
    assert len(wf.steps) == 2
    assert wf.steps[0].name == "CheckEligibility"
    assert wf.steps[0].execute is not None
    assert wf.steps[0].execute.policy_name == "StudentEligibility"
    assert len(wf.steps[0].transitions) == 2
    print("  ✓ test_parser_full_program passed")


def test_parser_ast_to_dict():
    """Test that AST can be serialized to dict (for JSON)."""
    tokens = Lexer(SIMPLE_POLICY).tokenize()
    ast = Parser(tokens).parse()
    d = ast.to_dict()
    assert d["node"] == "Program"
    assert len(d["policies"]) == 1
    assert d["policies"][0]["node"] == "Policy"
    # Ensure it's JSON-serializable
    json_str = json.dumps(d)
    assert len(json_str) > 0
    print("  ✓ test_parser_ast_to_dict passed")


def test_parser_syntax_error():
    """Test syntax error handling."""
    try:
        tokens = Lexer("policy {").tokenize()
        Parser(tokens).parse()
        assert False, "Should have raised ParserError"
    except ParserError as e:
        assert "Expected policy name" in str(e)
    print("  ✓ test_parser_syntax_error passed")


# ── Semantic Analysis Tests ───────────────────────────────────────────────────

def test_semantic_valid_program():
    """Test that a valid program passes semantic analysis."""
    tokens = Lexer(VALID_PROGRAM).tokenize()
    ast = Parser(tokens).parse()
    errors = SemanticAnalyzer().analyze(ast)
    assert len(errors) == 0, f"Unexpected errors: {[str(e) for e in errors]}"
    print("  ✓ test_semantic_valid_program passed")


def test_semantic_duplicate_policy():
    """Test detection of duplicate policy names."""
    source = """
    policy A { input x: number rule r: x >= 1 evaluate: r }
    policy A { input y: number rule r: y >= 1 evaluate: r }
    """
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    errors = SemanticAnalyzer().analyze(ast)
    assert any("Duplicate policy" in e.message for e in errors)
    print("  ✓ test_semantic_duplicate_policy passed")


def test_semantic_undefined_input():
    """Test detection of undefined input reference in a rule."""
    source = """
    policy A {
        input x: number
        rule r: undefined_var >= 1
        evaluate: r
    }
    """
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    errors = SemanticAnalyzer().analyze(ast)
    assert any("Undefined input" in e.message for e in errors)
    print("  ✓ test_semantic_undefined_input passed")


def test_semantic_undefined_policy_ref():
    """Test detection of undefined policy reference in workflow."""
    source = """
    policy A { input x: number rule r: x >= 1 evaluate: r }
    workflow W {
        step S1 {
            execute policy NonExistent
            on pass -> done
        }
    }
    """
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    errors = SemanticAnalyzer().analyze(ast)
    assert any("Undefined policy" in e.message for e in errors)
    print("  ✓ test_semantic_undefined_policy_ref passed")


def test_semantic_type_mismatch():
    """Test detection of type mismatch in comparison."""
    source = """
    policy A {
        input name: string
        rule r: name >= 10
        evaluate: r
    }
    """
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    errors = SemanticAnalyzer().analyze(ast)
    assert any("Type mismatch" in e.message for e in errors)
    print("  ✓ test_semantic_type_mismatch passed")


# ── Interpreter Tests ─────────────────────────────────────────────────────────

def test_interpreter_policy_pass():
    """Test policy evaluation that should pass."""
    tokens = Lexer(VALID_PROGRAM).tokenize()
    ast = Parser(tokens).parse()
    interp = Interpreter(ast)
    result = interp.evaluate_policy("StudentEligibility", {
        "gpa": 3.5, "credits": 45, "is_enrolled": True
    })
    assert result["passed"] == True
    assert result["rules"]["min_gpa"] == True
    assert result["rules"]["min_credits"] == True
    assert result["rules"]["active"] == True
    print("  ✓ test_interpreter_policy_pass passed")


def test_interpreter_policy_fail():
    """Test policy evaluation that should fail."""
    tokens = Lexer(VALID_PROGRAM).tokenize()
    ast = Parser(tokens).parse()
    interp = Interpreter(ast)
    result = interp.evaluate_policy("StudentEligibility", {
        "gpa": 2.5, "credits": 45, "is_enrolled": True
    })
    assert result["passed"] == False
    assert result["rules"]["min_gpa"] == False
    print("  ✓ test_interpreter_policy_fail passed")


def test_interpreter_workflow_pass():
    """Test successful workflow execution."""
    tokens = Lexer(VALID_PROGRAM).tokenize()
    ast = Parser(tokens).parse()
    interp = Interpreter(ast)
    result = interp.run_workflow("EnrollmentProcess", {
        "gpa": 3.5, "credits": 45, "is_enrolled": True
    })
    assert result["status"] == "completed"
    assert len(result["trace"]) > 0
    print("  ✓ test_interpreter_workflow_pass passed")


def test_interpreter_workflow_reject():
    """Test workflow execution that results in rejection."""
    tokens = Lexer(VALID_PROGRAM).tokenize()
    ast = Parser(tokens).parse()
    interp = Interpreter(ast)
    result = interp.run_workflow("EnrollmentProcess", {
        "gpa": 2.0, "credits": 10, "is_enrolled": False
    })
    assert result["status"] == "rejected"
    assert "does not meet" in result["message"]
    print("  ✓ test_interpreter_workflow_reject passed")


# ── Code Generation Tests ────────────────────────────────────────────────────

def test_codegen_produces_valid_python():
    """Test that generated Python code is syntactically valid."""
    tokens = Lexer(VALID_PROGRAM).tokenize()
    ast = Parser(tokens).parse()
    code = CodeGenerator().generate(ast)
    assert len(code) > 0
    # Verify it's valid Python by compiling it
    compile(code, '<test>', 'exec')
    print("  ✓ test_codegen_produces_valid_python passed")


def test_codegen_contains_functions():
    """Test that generated code contains expected function definitions."""
    tokens = Lexer(VALID_PROGRAM).tokenize()
    ast = Parser(tokens).parse()
    code = CodeGenerator().generate(ast)
    assert "def student_eligibility" in code
    assert "def enrollment_process" in code
    print("  ✓ test_codegen_contains_functions passed")


# ── Full Pipeline Tests ───────────────────────────────────────────────────────

def test_compile_full_pipeline():
    """Test the complete compiler pipeline."""
    result = compile_dsl(VALID_PROGRAM, {
        "gpa": 3.5, "credits": 45, "is_enrolled": True
    })
    assert len(result["tokens"]) > 0
    assert result["ast"] is not None
    assert result["semantic"]["valid"] == True
    assert result["execution"] is not None
    assert result["execution"]["status"] == "completed"
    assert len(result["generated_code"]) > 0
    assert len(result["errors"]) == 0
    print("  ✓ test_compile_full_pipeline passed")


def test_compile_with_errors():
    """Test pipeline with semantic errors."""
    bad_source = """
    policy A {
        input x: number
        rule r: undefined_var >= 1
        evaluate: r
    }
    """
    result = compile_dsl(bad_source)
    assert result["semantic"]["valid"] == False
    assert len(result["semantic"]["errors"]) > 0
    print("  ✓ test_compile_with_errors passed")


# ── Run All Tests ─────────────────────────────────────────────────────────────

def run_all():
    print("=" * 60)
    print("  DSL Compiler Test Suite")
    print("=" * 60)

    print("\n📋 Lexer Tests:")
    test_lexer_basic_tokens()
    test_lexer_keywords()
    test_lexer_operators()
    test_lexer_string_literal()
    test_lexer_number_literal()
    test_lexer_line_tracking()
    test_lexer_comments()
    test_lexer_error()

    print("\n🌳 Parser Tests:")
    test_parser_simple_policy()
    test_parser_full_program()
    test_parser_ast_to_dict()
    test_parser_syntax_error()

    print("\n🔍 Semantic Analysis Tests:")
    test_semantic_valid_program()
    test_semantic_duplicate_policy()
    test_semantic_undefined_input()
    test_semantic_undefined_policy_ref()
    test_semantic_type_mismatch()

    print("\n▶️  Interpreter Tests:")
    test_interpreter_policy_pass()
    test_interpreter_policy_fail()
    test_interpreter_workflow_pass()
    test_interpreter_workflow_reject()

    print("\n🐍 Code Generation Tests:")
    test_codegen_produces_valid_python()
    test_codegen_contains_functions()

    print("\n🔗 Full Pipeline Tests:")
    test_compile_full_pipeline()
    test_compile_with_errors()

    print("\n" + "=" * 60)
    print("  ✅ All 22 tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
