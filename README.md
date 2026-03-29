# 🛠️ Policy & Workflow DSL Compiler

A full-featured **Domain-Specific Language (DSL) compiler** for defining and executing **business policies** and **workflows**. The compiler features a complete 5-stage compilation pipeline, an AI-powered natural language interface using Google Gemini, and a command-line interface.

---

## 📌 Project Overview

The project implements the **complete compiler pipeline** and exposes it through a **command-line interface**.

- Core compiler engine (Lexer → Parser → Semantic Analyzer → Code Generator → Interpreter)
- Interactive CLI for writing DSL code or natural language descriptions
- AI-powered NLP translation (natural language → DSL) via Google Gemini
- Python code generation from DSL source
- Comprehensive test suite

**Entry points:** `cli.py` (interactive terminal)

---

## ✨ Features

- **Custom DSL** — Purpose-built language for defining policies (rules & conditions) and workflows (step-by-step processes)
- **5-Stage Compilation Pipeline** — Lexer → Parser → Semantic Analyzer → Code Generator → Interpreter
- **AI-Powered NLP Translation** — Converts plain English descriptions into valid DSL code using Google Gemini
- **Python Code Generation** — Compiles DSL programs into equivalent, runnable Python source code
- **Runtime Interpreter** — Evaluates policies and executes workflows with real inputs and execution tracing

- **CLI Mode** — Terminal-based interface for quick DSL compilation and testing
- **Comprehensive Test Suite** — 20+ unit tests covering every stage of the pipeline

---

## 📁 Project Structure

```
DSL Compiler/
├── cli.py                   # Interactive CLI with NLP support
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (GEMINI_API_KEY)
├── .gitignore
│
├── src/                     # Core compiler modules
│   ├── __init__.py
│   ├── lexer.py             # Stage 1: Lexical analysis (tokenizer)
│   ├── parser.py            # Stage 2: Recursive-descent parser → AST
│   ├── ast_nodes.py         # AST node definitions (dataclasses)
│   ├── semantic.py          # Stage 3: Semantic analysis & validation
│   ├── codegen.py           # Stage 4: Python code generation
│   ├── interpreter.py       # Stage 5: AST-walking interpreter
│   ├── compiler.py          # Pipeline orchestrator (ties all stages together)
│   └── nlp_parser.py        # NLP-to-DSL translation via Google Gemini
│
├── examples/
│   └── enrollment.dsl       # Sample DSL: Student enrollment policies & workflow
│
└── tests/
    └── test_compiler.py     # Comprehensive test suite
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**
- **Google Gemini API Key** (for NLP features)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "DSL Compiler"
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY="your-gemini-api-key-here"
   ```

---

## 🖥️ Usage

### Interactive CLI (`cli.py`)

Full-featured terminal interface with NLP support:

```bash
python cli.py
```

- Type DSL code or plain English descriptions
- Automatic NLP-to-DSL translation for natural language input
- Displays generated DSL, semantic validation, and Python output
- Press Enter on an empty line to submit
- Type `exit` or `quit` to stop

---

## 📝 DSL Syntax

### Policies

A **policy** defines input parameters, named rules (conditions), and an evaluation expression:

```dsl
policy StudentEligibility {
    input gpa: number
    input credits: number
    input is_enrolled: boolean

    rule min_gpa: gpa >= 3.0
    rule min_credits: credits >= 30
    rule active: is_enrolled == true

    evaluate: min_gpa AND min_credits AND active
}
```

### Workflows

A **workflow** defines a sequence of steps that execute policies or actions, with transitions based on outcomes:

```dsl
workflow EnrollmentProcess {
    step CheckEligibility {
        execute policy StudentEligibility
        on pass -> next
        on fail -> reject "Student does not meet eligibility requirements"
    }

    step AssignCourses {
        action "Assign student to selected courses"
        on complete -> next
    }

    step NotifyStudent {
        action "Send enrollment confirmation email"
        on complete -> done
    }
}
```

### Language Reference

| Construct         | Syntax                                     | Description                              |
| ----------------- | ------------------------------------------ | ---------------------------------------- |
| **Policy**        | `policy Name { ... }`                      | Defines a policy block                   |
| **Workflow**      | `workflow Name { ... }`                    | Defines a workflow block                 |
| **Input**         | `input name: type`                         | Declares a typed input parameter         |
| **Rule**          | `rule name: expression`                    | Defines a named boolean condition        |
| **Evaluate**      | `evaluate: logic_expression`               | Combines rules with logic operators      |
| **Step**          | `step Name { ... }`                        | Defines a workflow step                  |
| **Execute**       | `execute policy Name`                      | Runs a policy within a step              |
| **Action**        | `action "description"`                     | Performs a named action within a step    |
| **Transition**    | `on pass/fail/complete -> next/done/reject` | Defines step outcome routing            |
| **Types**         | `number`, `string`, `boolean`              | Supported data types                     |
| **Logic Ops**     | `AND`, `OR`, `NOT`                         | Logical operators (must be uppercase)    |
| **Comparison Ops** | `==`, `!=`, `>`, `<`, `>=`, `<=`          | Comparison operators                     |
| **Arithmetic Ops** | `+`, `-`, `*`, `/`                        | Arithmetic operators                     |
| **Comments**      | `// comment`                               | Single-line comments                     |

---

## ⚙️ Compiler Pipeline

The compiler processes DSL source code through **five sequential stages**:

```
┌─────────────┐    ┌──────────┐    ┌───────────┐    ┌───────────┐    ┌─────────────┐
│   Source     │───▶│  Lexer   │───▶│  Parser   │───▶│ Semantic  │───▶│  Code Gen   │
│   Code      │    │          │    │           │    │ Analyzer  │    │  (Python)   │
└─────────────┘    └──────────┘    └───────────┘    └───────────┘    └─────────────┘
                    Tokens          AST              Validated AST    Python Code
                                                                          │
                                                                          ▼
                                                                   ┌─────────────┐
                                                                   │ Interpreter │
                                                                   │ (Runtime)   │
                                                                   └─────────────┘
```

### Stage 1 — Lexer (`src/lexer.py`)

Converts raw source text into a flat list of **tokens**. Each token carries a type, value, line number, and column number. Handles keywords, identifiers, literals (numbers, strings), operators, delimiters, and comments.

### Stage 2 — Parser (`src/parser.py`)

A **recursive-descent parser** that consumes the token stream and builds an **Abstract Syntax Tree (AST)** using the node classes defined in `src/ast_nodes.py`. The grammar supports policies, workflows, expressions, and control flow.

### Stage 3 — Semantic Analyzer (`src/semantic.py`)

Performs **static validation** on the AST, catching errors such as:
- Duplicate policy, workflow, input, or rule names
- Undefined identifier references in rules and evaluate expressions
- Undefined policy references in workflow steps
- Type mismatches in comparisons
- Missing `evaluate` statements in policies

Uses a **symbol table** to track declared symbols across scopes.

### Stage 4 — Code Generator (`src/codegen.py`)

Traverses the AST and produces equivalent, **runnable Python source code**:
- Policies are compiled into Python functions returning `True`/`False`
- Workflows are compiled into Python functions that call policy functions, print actions, and follow transitions

### Stage 5 — Interpreter (`src/interpreter.py`)

An **AST-walking interpreter** that can:
- **Evaluate policies** given input values → returns pass/fail with per-rule details
- **Execute workflows** step-by-step, following transitions based on policy outcomes
- Generate **execution traces** for debugging and visualization

---

## 🤖 AI-Powered NLP Translation

The compiler integrates with **Google Gemini** (`src/nlp_parser.py`) to translate plain English descriptions into valid DSL code. 

**Example input:**
> "Create a policy that checks if a student has a GPA above 3.0 and has completed at least 30 credits"

**Generated DSL output:**
```dsl
policy StudentCheck {
    input gpa: number
    input credits: number

    rule high_gpa: gpa > 3.0
    rule enough_credits: credits >= 30

    evaluate: high_gpa AND enough_credits
}
```

This feature is available in the **CLI**.

---

## 🧪 Testing

Run the full test suite:

```bash
python -m pytest tests/test_compiler.py -v
```

The test suite covers:

| Category             | Tests                                                          |
| -------------------- | -------------------------------------------------------------- |
| **Lexer**            | Token types, keywords, operators, literals, line tracking, comments, error handling |
| **Parser**           | Simple policy, full program, AST serialization, syntax errors  |
| **Semantic Analysis** | Valid programs, duplicate names, undefined references, type mismatches |
| **Interpreter**      | Policy pass/fail, workflow execution, workflow rejection       |
| **Code Generation**  | Valid Python output, function definitions                      |
| **Full Pipeline**    | End-to-end compilation, error propagation                      |

---

## 👥 Team Contributions

The project work is divided among **4 team members**. Each member is responsible for **at least one core compiler stage** along with supporting modules:

| Member | Core Compiler Stage(s) | Additional Responsibilities | Key Files |
| ------ | ---------------------- | --------------------------- | --------- |
| **Rohit** | Lexer + AST Design | Token definitions | `src/lexer.py`, `src/ast_nodes.py` |
| **Vibhi** | Parser + Semantic Analysis | Grammar design, static validation | `src/parser.py`, `src/semantic.py` |
| **Lokendra** | Interpreter | NLP translation, pipeline orchestration | `src/interpreter.py`, `src/nlp_parser.py`, `src/compiler.py` |
| **Vibhu** | Code Generator | CLI interface, testing | `src/codegen.py`, `cli.py`, `tests/test_compiler.py` |

### Rohit — Lexer & AST Design (Compiler Frontend)

- **Core:** Designed and implemented the **tokenizer** (`lexer.py`) — converts raw DSL source into typed tokens with line/column tracking
- **Core:** Defined all **AST node classes** (`ast_nodes.py`) — dataclass-based nodes for policies, workflows, expressions, and control flow
- Designed the token type system (keywords, operators, literals, delimiters)

### Vibhi — Parser & Semantic Analysis

- **Core:** Built the **recursive-descent parser** (`parser.py`) — transforms the token stream into an Abstract Syntax Tree
- **Core:** Implemented the **semantic analyzer** (`semantic.py`) — validates the AST for correctness (duplicate names, undefined references, type mismatches)
- Designed the DSL grammar rules and expression precedence
- Built the **symbol table** for tracking declarations across scopes
- Handled syntax and semantic error reporting with precise source locations

### Lokendra — Interpreter & AI/NLP Integration

- **Core:** Developed the **AST-walking interpreter** (`interpreter.py`) — evaluates policies and executes workflows at runtime
- Implemented **execution tracing** for debugging and visualization
- Integrated **Google Gemini AI** (`nlp_parser.py`) for natural language to DSL translation
- Built the **pipeline orchestrator** (`compiler.py`) that ties all five stages together

### Vibhu — Code Generator, CLI & Testing

- **Core:** Built the **Python code generator** (`codegen.py`) — traverses the AST and emits equivalent, runnable Python code
- Created the **interactive CLI** (`cli.py`) with multi-line input and NLP support
- Wrote the **comprehensive test suite** (`tests/test_compiler.py`) — 20+ tests covering all pipeline stages

### Phase-wise Role Division

#### Phase 1 — CLI-Based Compiler

| Member | Phase 1 Contributions |
| ------ | --------------------- |
| **Rohit** | Built the **Lexer** (`lexer.py`) and designed all **AST node classes** (`ast_nodes.py`) |
| **Vibhi** | Built the **Parser** (`parser.py`) and **Semantic Analyzer** (`semantic.py`) with symbol table |
| **Lokendra** | Built the **Interpreter** (`interpreter.py`), **NLP Parser** (`nlp_parser.py`), and **Pipeline Orchestrator** (`compiler.py`) |
| **Vibhu** | Built the **Code Generator** (`codegen.py`), **CLI interface** (`cli.py`), and **Test Suite** (`test_compiler.py`) |


---

## 📦 Dependencies

| Package          | Purpose                                          |
| ---------------- | ------------------------------------------------ |
| `google-genai`   | Google Gemini AI SDK for NLP-to-DSL translation  |
| `python-dotenv`  | Loads environment variables from `.env` file     |

---

## 📄 License

This project is developed for academic/research purposes.
