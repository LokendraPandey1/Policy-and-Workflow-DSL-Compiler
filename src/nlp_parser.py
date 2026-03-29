import os
import re

try:
    from dotenv import load_dotenv
    load_dotenv()
    
    from google import genai
    client = genai.Client() if os.environ.get("GEMINI_API_KEY") else None
except ImportError:
    client = None


def convert_nl_to_dsl(nl_text: str) -> tuple[str, str]:
    """
    Translates a natural language string into valid DSL using Google Gemini.
    Returns (generated_dsl, error_message).
    """
    if not client:
        return "", "Error: GEMINI_API_KEY environment variable is not set or google-genai is not installed. NLP is disabled."
    
    prompt = f"""
You are a specialised compiler assistant for a custom Policy & Workflow DSL.
Translate the following natural language request into strict, valid DSL code.
Produce ONLY the DSL code, no markdown blocks, no formatting, no explanations.

Rules:
1. Policy format MUST STRICTLY MATCH: 
policy Name {{
    input name: type
    rule rule_name: condition
    evaluate: bool_expr
}}
2. Workflow format MUST STRICTLY MATCH: 
workflow Name {{
    step Name {{
        execute policy Name
        on pass -> next
        on fail -> reject "msg"
    }}
}}
3. Types available: number, string, boolean
4. DO NOT USE COMMAS (`,`) between statements, inputs, or rules. Newlines or spaces are enough.
5. Use ONLY ASCII operators (`>=`, `<=`, `==`, `!=`, `<`, `>`). DO NOT use symbols like `≥` or `≤`.
6. Logical operators MUST be uppercase: `AND`, `OR`, `NOT`.
7. Boolean values MUST be lowercase: `true`, `false`.
8. Output must be raw text.
9. An Action step in a workflow MUST use the `action "description"` syntax instead of `execute policy`.
10. Ensure ALL steps mentioned in the natural language are actually generated in the workflow block.

User Request:
{nl_text}
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        dsl = response.text
        # Strip markdown if it snuck in
        if "```" in dsl:
            dsl = re.sub(r'```(?:dsl|text)?', '', dsl)
            dsl = re.sub(r'```', '', dsl)
        return dsl.strip(), ""
    except Exception as e:
        return "", f"AI generation error: {str(e)}"
