import os
import re
from typing import Tuple

from src.compiler import compile_dsl

try:
    from dotenv import load_dotenv

    load_dotenv()

    from google import genai

    client = genai.Client() if os.environ.get("GEMINI_API_KEY") else None
except ImportError:
    client = None


SYSTEM_PROMPT = """
You are a specialised compiler assistant for a custom Policy & Workflow DSL.
Translate the user's natural language request into strict, valid DSL code.
Produce ONLY the DSL code, with no markdown, comments, headings, bullets, or explanations.

The DSL must obey these rules exactly:
1. A policy must look like:
policy Name {
    input name: type
    rule rule_name: condition
    evaluate: bool_expr
}
2. A workflow must look like:
workflow Name {
    step Name {
        execute policy Name
        on pass -> next
        on fail -> reject "message"
    }
}
3. Action steps must use:
action "description"
on complete -> next
4. Types are only: number, string, boolean
5. Logical operators must be uppercase: AND, OR, NOT
6. Boolean values must be lowercase: true, false
7. Use only ASCII operators: >= <= == != > <
8. If multiple policies are requested, generate all of them before the workflow.
9. Every mentioned policy, workflow, step, rule, and transition must be included.
10. In workflow steps, always use the exact phrase `execute policy PolicyName`.
11. Reject transitions must use the exact form `on fail -> reject "message"`.
12. Successful action transitions must use `on complete -> next` or `on complete -> done`.
"""


def _strip_markdown_blocks(text: str) -> str:
    if "```" in text:
        text = re.sub(r"```(?:dsl|text)?", "", text)
        text = re.sub(r"```", "", text)
    return text


def _normalize_quotes_and_operators(text: str) -> str:
    replacements = {
        "\u201c": '"',
        "\u201d": '"',
        "\u2018": "'",
        "\u2019": "'",
        "\u2265": ">=",
        "\u2264": "<=",
        "\u2192": "->",
        "\u2013": "-",
        "\u2014": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _extract_dsl_region(text: str) -> str:
    match = re.search(r"\b(policy|workflow)\b", text)
    if match:
        text = text[match.start():]
    return text.strip()


def _repair_common_dsl_issues(text: str) -> str:
    text = _strip_markdown_blocks(text)
    text = _normalize_quotes_and_operators(text)
    text = _extract_dsl_region(text)

    # Common LLM slip: "execute PolicyName" instead of "execute policy PolicyName"
    text = re.sub(r"\bexecute\s+(?!policy\b)([A-Za-z_][A-Za-z0-9_]*)", r"execute policy \1", text)

    text = re.sub(r"\s*-\s*>\s*", " -> ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _validate_generated_dsl(dsl: str) -> Tuple[bool, str]:
    result = compile_dsl(dsl)
    if result.get("errors"):
        first_error = result["errors"][0]
        return False, f"{first_error.get('stage', 'unknown')}: {first_error.get('message', 'Unknown error')}"
    return True, ""


def _generate_with_prompt(prompt: str) -> tuple[str, str]:
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text or "", ""
    except Exception as e:
        return "", f"AI generation error: {str(e)}"


def convert_nl_to_dsl(nl_text: str) -> tuple[str, str]:
    """
    Translates a natural language string into valid DSL using Google Gemini.
    Returns (generated_dsl, error_message).
    """
    if not client:
        return "", "Error: GEMINI_API_KEY environment variable is not set or google-genai is not installed. NLP is disabled."

    prompt = f"""{SYSTEM_PROMPT}

User Request:
{nl_text}
"""
    raw_dsl, err = _generate_with_prompt(prompt)
    if err:
        return "", err

    cleaned_dsl = _repair_common_dsl_issues(raw_dsl)
    is_valid, validation_error = _validate_generated_dsl(cleaned_dsl)
    if is_valid:
        return cleaned_dsl, ""

    repair_prompt = f"""{SYSTEM_PROMPT}

The previous draft was invalid. Repair it into valid DSL.
Return only corrected DSL.

Validation error:
{validation_error}

Previous DSL draft:
{cleaned_dsl}

Original user request:
{nl_text}
"""
    repaired_dsl, err = _generate_with_prompt(repair_prompt)
    if err:
        return "", err

    repaired_dsl = _repair_common_dsl_issues(repaired_dsl)
    is_valid, validation_error = _validate_generated_dsl(repaired_dsl)
    if is_valid:
        return repaired_dsl, ""

    return "", f"AI generated DSL but it is still invalid after repair attempt: {validation_error}"
