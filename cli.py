import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.compiler import compile_dsl
from src.nlp_parser import convert_nl_to_dsl


def main():
    print("=" * 60)
    print("  DSL Compiler AI Assistant (CLI Mode)")
    print("  Type 'exit' or 'quit' to stop.")
    print("=" * 60)

    while True:
        try:
            # Multi-line input for the CLI
            print("\nEnter natural language description or raw DSL:")
            print("(Press Enter on an empty line to submit)")
            lines = []
            while True:
                line = input()
                if not line:
                    break
                lines.append(line)

            source = "\n".join(lines).strip()

            if source.lower() in ["exit", "quit"]:
                break
            
            if not source:
                continue

            print("\n⚙️  Processing...")

            # 1. NLP Translation
            looks_like_dsl = "{" in source and ("policy" in source or "workflow" in source)
            if not looks_like_dsl:
                converted_dsl, err = convert_nl_to_dsl(source)
                if err:
                    print(f"\n❌ AI Translation Failed: {err}")
                    continue
                print("\n✨ Generated DSL:")
                print(converted_dsl)
                source = converted_dsl

            # 2. Compilation
            print("\n⚙️  Compiling...")
            result = compile_dsl(source)

            # 3. Output
            print("\n" + "="*50)
            print("             COMPILER PIPELINE RESULTS")
            print("="*50)

            print("\n[1] LEXER")
            if result.get("tokens"):
                tokens = result["tokens"]
                print(f"  Generated {len(tokens)} tokens.")
                import textwrap
                tok_strs = [f"{t['type']}({repr(t['value'])})" for t in tokens]
                print(textwrap.fill(" ".join(tok_strs), width=80, initial_indent="  ", subsequent_indent="  "))

            print("\n[2] PARSER")
            if result.get("ast"):
                ast_dict = result["ast"]
                print("  ✅ AST generated successfully.")
                print(f"    Policies : {len(ast_dict.get('policies', []))}")
                print(f"    Workflows: {len(ast_dict.get('workflows', []))}")

            print("\n[3] SEMANTIC ANALYZER")
            if result.get("semantic", {}).get("valid"):
                print("  ✅ PASS: No semantic errors found.")
            else:
                print("  ❌ FAIL: Semantic errors detected:")
                for e in result.get("semantic", {}).get("errors", []):
                    print(f"    - {e['message']} (Line {e.get('line', 'unknown')})")

            print("\n[4] CODE GENERATOR")
            if result.get("generated_code"):
                print("  ✅ Python Code:\n")
                print("-" * 50)
                print(result["generated_code"])
                print("-" * 50)
                
            print("\n[5] INTERPRETER")
            print("  (Execution skipped in CLI mode - no runtime inputs provided)")

            if result.get("errors"):
                print("\n❌ FATAL COMPILATION ERRORS:")
                for e in result["errors"]:
                    print(f"  [{e.get('stage', 'unknown').upper()}]: {e.get('message')}")

        except KeyboardInterrupt:
            break
        except EOFError:
            break
        except Exception as e:
            print(f"\nUnexpected error: {e}")

    print("\nGoodbye!")

if __name__ == "__main__":
    main()
