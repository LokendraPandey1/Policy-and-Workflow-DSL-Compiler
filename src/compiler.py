"""
Compiler Pipeline Orchestrator.

Ties together all compiler stages into a single `compile()` function
that returns structured results from every stage.
"""

import json
from typing import Dict, Any, List, Optional
from src.lexer import Lexer, LexerError, Token
from src.parser import Parser, ParserError
from src.semantic import SemanticAnalyzer
from src.interpreter import Interpreter, ExecutionError
from src.codegen import CodeGenerator
from src.ast_nodes import Program


def compile_dsl(source: str, inputs: Dict[str, Any] = None, workflow_name: str = None) -> Dict[str, Any]:
    """
    Run the full compiler pipeline on DSL source code.

    Args:
        source:        DSL source code string.
        inputs:        Dict of input values for policy evaluation / workflow execution.
        workflow_name: Name of the workflow to execute (optional).

    Returns:
        A dict with results from each stage:
        {
            "source": str,
            "tokens": [...],
            "ast": {...},
            "semantic": {"valid": bool, "errors": [...]},
            "execution": {...} or None,
            "generated_code": str,
            "errors": [...]
        }
    """
    result = {
        "source": source,
        "tokens": [],
        "ast": None,
        "semantic": {"valid": False, "errors": []},
        "execution": None,
        "generated_code": "",
        "errors": [],
    }

    # ── Stage 1: Lexical Analysis ─────────────────────────────────────────
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        result["tokens"] = [t.to_dict() for t in tokens]
    except LexerError as e:
        result["errors"].append({"stage": "lexer", "message": str(e)})
        return result

    # ── Stage 2: Parsing ──────────────────────────────────────────────────
    try:
        parser = Parser(tokens)
        ast = parser.parse()
        result["ast"] = ast.to_dict()
    except ParserError as e:
        result["errors"].append({"stage": "parser", "message": str(e)})
        return result

    # ── Stage 3: Semantic Analysis ────────────────────────────────────────
    analyzer = SemanticAnalyzer()
    sem_errors = analyzer.analyze(ast)
    if sem_errors:
        result["semantic"] = {
            "valid": False,
            "errors": [e.to_dict() for e in sem_errors],
        }
        # Don't stop — still attempt code generation for pedagogical value
    else:
        result["semantic"] = {"valid": True, "errors": []}

    # ── Stage 4: Code Generation ──────────────────────────────────────────
    try:
        codegen = CodeGenerator()
        result["generated_code"] = codegen.generate(ast)
    except Exception as e:
        result["errors"].append({"stage": "codegen", "message": str(e)})

    # ── Stage 5: Execution (only if inputs provided and semantically valid) ──
    if inputs and result["semantic"]["valid"]:
        try:
            interpreter = Interpreter(ast)

            if workflow_name:
                exec_result = interpreter.run_workflow(workflow_name, inputs)
            elif ast.workflows:
                exec_result = interpreter.run_workflow(ast.workflows[0].name, inputs)
            elif ast.policies:
                exec_result = interpreter.evaluate_policy(ast.policies[0].name, inputs)
            else:
                exec_result = {"message": "No workflows or policies to execute"}

            result["execution"] = exec_result
        except ExecutionError as e:
            result["errors"].append({"stage": "execution", "message": str(e)})
        except Exception as e:
            result["errors"].append({"stage": "execution", "message": str(e)})

    return result
