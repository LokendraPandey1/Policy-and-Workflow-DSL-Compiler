import sys
import os

# Add project root to path so 'src' package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.compiler import compile_dsl

def main():
    example_path = os.path.join(os.path.dirname(__file__), "examples", "enrollment.dsl")
    
    if not os.path.exists(example_path):
        print(f"Error: Could not find example DSL at {example_path}")
        return

    print(f"Reading DSL from: {example_path}")
    with open(example_path, "r") as f:
        source = f.read()

    print("\nCompiling DSL...\n")
    # For a simple demo, we won't provide inputs, just generate the code
    result = compile_dsl(source)
    
    if result.get("errors"):
        print("=== Compilation Errors ===")
        for error in result["errors"]:
            print(f"[{error.get('stage', 'unknown')}]: {error.get('message', 'No message')}")
        
        # If there's still generated code (parser/semantic might recover), we can print it
        if not result.get("generated_code"):
            return

    print("=== Generated Python Code ===")
    print(result["generated_code"])
    print("=============================")

if __name__ == "__main__":
    main()
