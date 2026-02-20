import sys
import os
from flask import Flask, request, jsonify, render_template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.compiler import compile_dsl

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/compile", methods=["POST"])
def compile_endpoint():
    try:
        data = request.get_json(force=True)
        source = data.get("source", "")
        # Compile DSL
        result = compile_dsl(source)
        
        # We only want the generated Python code or errors
        response_data = {}
        if result.get("errors"):
            errors_str = "\n".join([f"[{e.get('stage', 'unknown')}]: {e.get('message', 'error')}" for e in result["errors"]])
            response_data["python_code"] = f"# Errors during compilation:\n{errors_str}\n\n"
            if result.get("generated_code"):
                response_data["python_code"] += result["generated_code"]
        else:
            response_data["python_code"] = result.get("generated_code", "# No code generated")
            
        return jsonify(response_data)
    except Exception as e:
        return jsonify({"python_code": f"# Server Error: {str(e)}"}), 500

@app.route("/example")
def example():
    example_path = os.path.join(os.path.dirname(__file__), "examples", "enrollment.dsl")
    if os.path.exists(example_path):
        with open(example_path, "r") as f:
            return jsonify({"source": f.read()})
    return jsonify({"source": "// Write DSL here\n"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
