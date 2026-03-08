# Agentic Synthetic Fraud Dataset Generator

A production-grade, LLM-powered pipeline that converts any fraud scenario description into a fully synthetic, realistic dataset — automatically.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Quick Start](#quick-start)
5. [Configuration](#configuration)
6. [Usage](#usage)
7. [Supported Fraud Scenarios](#supported-fraud-scenarios)
8. [Blueprint Schema](#blueprint-schema)
9. [Extending the System](#extending-the-system)
10. [Troubleshooting](#troubleshooting)

---

## Overview

This system uses a **multi-agent LLM pipeline** to:

1. Parse a natural-language fraud scenario
2. Generate a detailed **Fraud Blueprint** (structured JSON)
3. Validate and auto-fix the blueprint
4. Generate a **Python data-generation script** from the blueprint
5. Execute the script (with automatic LLM-powered error recovery)
6. Output a production-ready **synthetic CSV/JSON/Parquet dataset**

### Supported LLM Backends

| Backend | Models |
|---------|--------|
| **Ollama** (local) | `llama2`, `qwen2.5-coder:7b` |
| **OpenAI-compatible** | Any model via `OPENAI_BASE_URL` |

---

## Architecture

```
User Input
    │
    ▼
┌─────────────────────────┐
│ ScenarioInterpreterAgent │  Rule-based + regex parser
└─────────────┬───────────┘
              │ scenario_params dict
              ▼
┌─────────────────────────┐
│  BlueprintGeneratorAgent │  LLM → JSON blueprint
└─────────────┬───────────┘
              │ raw blueprint
              ▼
┌─────────────────────────┐
│  BlueprintValidatorAgent │  JSON-Schema + business rules
└─────────────┬───────────┘
              │ validated blueprint  (loop-fix on failure)
              ▼
┌─────────────────────────┐
│   CodeGeneratorAgent    │  LLM → Python data-gen script
└─────────────┬───────────┘
              │ generated code
              ▼
┌─────────────────────────┐
│    ExecutionEngine      │  subprocess isolation
└─────────────┬───────────┘
              │ error?
              ▼
┌─────────────────────────┐
│     ErrorFixAgent       │  LLM loop (up to MAX_CODE_RETRIES)
└─────────────┬───────────┘
              │ fixed code → re-execute
              ▼
     Synthetic Dataset 🎉
```

---

## Project Structure

```
fraud_generator/
├── main.py                          # Entry point
├── requirements.txt
├── .env.example                     # Copy to .env and configure
│
├── config/
│   └── model_config.py              # All tuneable parameters
│
├── agents/
│   ├── scenario_interpreter.py      # Parse user text input
│   ├── blueprint_generator.py       # LLM → blueprint JSON
│   ├── blueprint_validator.py       # Validate blueprint
│   ├── code_generator.py            # LLM → Python code
│   └── error_fix_agent.py           # LLM error recovery
│
├── core/
│   ├── llm_interface.py             # Unified LLM API wrapper
│   ├── execution_engine.py          # Safe subprocess runner
│   └── pipeline.py                  # Full orchestration
│
├── schemas/
│   └── blueprint_schema.py          # JSON-Schema definition
│
├── prompts/
│   ├── blueprint_prompt.py          # Blueprint generation prompt
│   ├── code_generation_prompt.py    # Code generation prompt
│   └── error_fix_prompt.py          # Error fix prompt
│
├── utils/
│   ├── logger.py                    # Colour + file logging
│   └── json_parser.py               # Robust JSON extraction
│
└── output/
    └── synthetic_datasets/          # All outputs land here
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running

### 2. Pull Required Models

```bash
ollama pull qwen2.5-coder:7b   # recommended (best at code generation)
ollama pull llama2              # alternative
```

### 3. Install Dependencies

```bash
cd fraud_generator
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env if you need non-default settings
```

### 5. Run

```bash
# Interactive mode
python main.py

# Demo mode (BIN Attack, 10k rows)
python main.py --demo

# One-liner CLI
python main.py --scenario "BIN Attack, 100000 rows, 5% fraud, csv"
```

---

## Configuration

All settings live in `config/model_config.py` and can be overridden via `.env`:

| Variable | Default | Description |
|---|---|---|
| `LLM_BACKEND` | `ollama` | `ollama` or `openai_compatible` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `PRIMARY_MODEL` | `qwen2.5-coder` | Model for blueprint generation |
| `CODE_MODEL` | `qwen2.5-coder` | Model for code generation & fixes |
| `LLM_TEMPERATURE` | `0.2` | Lower = more deterministic |
| `LLM_MAX_TOKENS` | `4096` | Max tokens per LLM call |
| `MAX_BLUEPRINT_RETRIES` | `3` | Blueprint validation fix rounds |
| `MAX_CODE_RETRIES` | `5` | Code execution fix attempts |
| `CODE_EXECUTION_TIMEOUT` | `120` | Script timeout in seconds |
| `OUTPUT_DIR` | `output/synthetic_datasets` | Where datasets are saved |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## Usage

### Interactive Mode

```
python main.py

▶ Fraud Scenario: BIN Attack
▶ Rows: 100000
▶ Fraud Ratio: 5%
▶ Output Format: CSV
▶ [blank line to submit]
```

### CLI Labelled Format

```bash
python main.py --scenario "
Fraud Scenario: Account Takeover
Rows: 50000
Fraud Ratio: 3%
Output Format: CSV
"
```

### CLI Inline Format

```bash
python main.py --scenario "Money Laundering, 20000, 2%, csv"
```

### Built-in Demos

```bash
python main.py --demo bin_attack
python main.py --demo card_testing
python main.py --demo account_takeover
python main.py --demo money_laundering
```

---

## Supported Fraud Scenarios

| Scenario | Fraud Type |
|---|---|
| BIN Attack | Card-Not-Present Fraud |
| Card Testing Fraud | Card-Not-Present Fraud |
| Account Takeover | Identity Fraud |
| Money Laundering | Financial Crime |
| Refund Fraud | Return / Refund Abuse |
| Identity Fraud | Identity Theft |
| Phishing | Social Engineering |
| Synthetic Identity | Identity Fraud |
| *Any custom text* | Generic Fraud |

---

## Blueprint Schema

Every generated blueprint follows this structure:

```json
{
  "Fraud_Scenario_Name": "BIN Attack",
  "Description": "...",
  "Fraud_Type": "Card-Not-Present Fraud",
  "Dataset_Specifications": {
    "total_rows": 100000,
    "fraud_ratio": 0.05,
    "output_format": "csv"
  },
  "Transaction_Structure": { ... },
  "Fraud_Patterns": [ ... ],
  "Behavioral_Rules": { ... },
  "Fraud_Characteristics": { ... },
  "Temporal_Patterns": { ... },
  "Data_Distribution": { ... },
  "Fraud_Indicators": [ ... ],
  "Synthetic_Data_Generation_Rules": {
    "normal_transactions": { ... },
    "fraud_transactions": { ... }
  },
  "Column_Definitions": { ... },
  "Edge_Cases": [ ... ],
  "Validation_Constraints": { ... }
}
```

Blueprints are saved to `output/synthetic_datasets/<scenario>_blueprint.json`.

---

## Output Files

For each run, the following files are created in `output/synthetic_datasets/`:

| File | Description |
|---|---|
| `<scenario>_synthetic_dataset.csv` | The final synthetic dataset |
| `<scenario>_blueprint.json` | The full fraud blueprint |
| `<scenario>_generator.py` | The generated Python script |
| `<scenario>_generator_fix{n}.py` | Fixed script versions (if errors occurred) |

---

## Extending the System

### Add a New LLM Backend

1. Edit `core/llm_interface.py` – add a new `_call_<backend>()` function.
2. Update `LLM_BACKEND` check in `generate_response()`.
3. Add the backend name to `.env.example`.

### Add a New Fraud Scenario

Add an entry to `KNOWN_SCENARIOS` in `agents/scenario_interpreter.py`:

```python
"wire fraud": {
    "fraud_type": "Financial Crime",
    "description": "Fraudulent wire transfers using compromised credentials."
}
```

### Customise Prompts

Edit files in `prompts/` – prompts are fully decoupled from agent logic.

---

## Troubleshooting

**Ollama connection refused**
```
Error: HTTPConnectionPool: Connection refused
```
Ensure Ollama is running: `ollama serve`

**Model not found**
```
Error: model 'qwen2.5-coder:7b' not found
```
Pull the model: `ollama pull qwen2.5-coder:7b`

**Blueprint validation fails repeatedly**
- Increase `MAX_BLUEPRINT_RETRIES` in `.env`
- Try `qwen2.5-coder` instead of `llama2` (better JSON output)
- Set `LLM_TEMPERATURE=0.1` for more deterministic output

**Code execution times out**
- Reduce `Rows` in your scenario
- Increase `CODE_EXECUTION_TIMEOUT` in `.env`

**Import errors in generated code**
- Ensure `faker`, `pandas`, `numpy` are installed in the same Python environment

---

## License

MIT
