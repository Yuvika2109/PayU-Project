# FraudSynth — Agentic Synthetic Fraud Dataset Generator

**PayU Risk Intelligence**

Presenation Link: https://docs.google.com/presentation/d/17bEoLXE2zWLTRfLDzdQOK7hoH6z0kGXL/edit?usp=sharing&ouid=116519170303998437026&rtpof=true&sd=true

The Demo video: https://drive.google.com/file/d/1eWgbSDuLR7EhNx7kVZTBoiDWkTNlhElC/view?usp=sharing     

FraudSynth is an LLM-powered pipeline that converts a plain-English fraud scenario description into a fully labelled synthetic transaction dataset — ready for rule engine testing, ML model training, and fraud research. No real customer data is ever used.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Fraud Categories Supported](#fraud-categories-supported)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the App](#running-the-app)
  - [Streamlit Web UI](#streamlit-web-ui)
  - [CLI — Interactive Mode](#cli--interactive-mode)
  - [CLI — One-liner Mode](#cli--one-liner-mode)
  - [CLI — Skip LLM (Blueprint Mode)](#cli--skip-llm-blueprint-mode)
- [Branch Guide](#branch-guide)
- [Output Format](#output-format)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)

---

## Overview

FraudSynth takes a fraud scenario description like:

> *"UPI collect scam, 500 rows, 15% fraud, amounts ₹200–₹1200, between 7pm and 11pm"*

and produces a CSV/JSON/Parquet dataset where:

- Every fraud transaction carries the exact behavioural signals the scenario implies (`collect_requests_1h`, `is_new_vpa`, `hour_of_day`, `amount`, etc.)
- Legitimate transactions follow realistic Indian UPI / EMVCo 3DS patterns
- Every row is ground-truth labelled (`fraud_label`, `fraud_type`)
- No LLM is involved in the actual data generation — the LLM only produces a **blueprint JSON** (a quantitative spec), and a fully deterministic engine builds the dataset from that spec

---

## Architecture

```
User Input (plain English / form / CLI)
        │
        ▼
┌──────────────────────────┐
│  ScenarioInterpreterAgent│  Extracts rows, ratio, scenario name, fraud type
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  BlueprintGeneratorAgent │  Ollama LLM → quantitative blueprint JSON
│  (Llama 3 / local LLM)   │  (amounts, timing, velocity, patterns)
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  BlueprintValidatorAgent │  Validates schema + enforces user row/ratio values
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│      DatasetEngine       │  Routes to specialist engine by fraud_category:
│                          │   • UPIDatasetEngine     (UPI Fraud)
│                          │   • DatasetEngine/3DS    (Card Fraud — EMVCo)
│                          │   • GenericDatasetEngine (Other Fraud)
└──────────┬───────────────┘
           │
           ▼
  CSV / JSON / Parquet
  + Blueprint JSON artifact
```

---

## Fraud Categories Supported

### Card Fraud — EMVCo 3DS
Generates transactions conforming to the EMVCo 3-D Secure v2.3.1 specification.

| Scenario | Description |
|---|---|
| BIN Attack | Rapid micro-transactions (₹0.01–₹2) testing BIN ranges — 15–80 per burst |
| Card Testing | Small test charges verifying stolen credentials before large purchases |
| Account Takeover | High-value chain of purchases from new device and foreign IP |
| Money Laundering | Structuring transactions under reporting thresholds via mule network |
| Phishing | Victim-authorised transfers to unusual recipients |
| Synthetic Identity | Slow credit build-up followed by bust-out |
| Friendly Fraud | Legitimate-looking purchases later disputed for chargeback |
| Triangulation Fraud | Burst of CNP transactions across multiple e-commerce merchants |
| Corporate Card Abuse | Above-policy amounts at travel/entertainment merchants |

### UPI Fraud — Indian UPI
Generates UPI transactions with realistic Indian VPAs, banks, apps, and behavioural signals.

| Scenario | Description |
|---|---|
| UPI Collect Scam | 3–8 rapid collect requests in 15–30 min window, posing as refund/cashback, ₹200–₹1200 |
| UPI Mule Transfers | Chained fund forwarding across 3–6 mule VPAs, off-hours, cross-state |
| UPI Credential Fraud | Stolen UPI PIN — high-value transfers from new device with suspicious IP |

### Other / Generic Fraud
Flexible engine for non-card, non-UPI scenarios including money laundering, identity fraud, refund abuse, and more.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Web UI | [Streamlit](https://streamlit.io/) |
| LLM Backend | [Ollama](https://ollama.com/) (local, no data leaves your machine) |
| Primary Model | `llama3` / `llama3.2:3b` (configurable) |
| Data Generation | Pandas 2.x, NumPy |
| Realistic Fakers | [Faker](https://faker.readthedocs.io/) |
| Blueprint Validation | jsonschema |
| Config | python-dotenv |
| Logging | colorlog |
| Output Formats | CSV, JSON, Parquet, Excel |

---

## Repository Structure

```
PayU-Project/
├── README.md
└── fraud_generator/
    ├── app.py                        # Streamlit web UI
    ├── main.py                       # CLI entry point
    ├── requirements.txt
    │
    ├── agents/
    │   ├── scenario_interpreter.py   # Parses user input → structured params
    │   ├── blueprint_generator.py    # LLM → blueprint JSON
    │   ├── blueprint_validator.py    # Validates blueprint schema
    │   ├── code_generator.py
    │   └── error_fix_agent.py
    │
    ├── core/
    │   ├── dataset_engine.py         # EMVCo 3DS card fraud engine + router
    │   ├── upi_dataset_engine.py     # UPI fraud engine (collect scam, mule, credential)
    │   ├── generic_dataset_engine.py # Generic / other fraud engine
    │   ├── pipeline.py               # End-to-end orchestration
    │   ├── llm_interface.py          # Ollama HTTP client
    │   └── execution_engine.py
    │
    ├── prompts/
    │   ├── blueprint_prompt.py       # LLM prompt templates (card / UPI / generic)
    │   └── ...
    │
    ├── schemas/
    │   ├── upi_schema.py             # UPI column definitions, Indian data pools
    │   ├── emvco_3ds_schema.py       # EMVCo 3DS column definitions
    │   └── ...
    │
    ├── config/
    │   └── model_config.py           # Ollama URL, model names, timeouts
    │
    ├── utils/
    │   ├── logger.py
    │   └── json_parser.py
    │
    └── output/
        └── synthetic_datasets/       # Generated datasets saved here
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| Ollama | latest | [Install from ollama.com](https://ollama.com/download) |
| llama3 model | — | Pulled via `ollama pull llama3` |
| Git | any | |
| 8 GB RAM | recommended | For running Llama 3 locally |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/PayU-Project.git
cd PayU-Project
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# or
venv\Scripts\activate           # Windows
```

### 3. Install Python dependencies

```bash
pip install -r fraud_generator/requirements.txt
```

### 4. Install and start Ollama

Download Ollama from [https://ollama.com/download](https://ollama.com/download) and install it.

Then pull the required model:

```bash
ollama pull llama3
```

Start the Ollama server (it may start automatically on install):

```bash
ollama serve
```

Verify it is running:

```bash
curl http://localhost:11434
# Expected: "Ollama is running"
```

### 5. (Optional) Create a `.env` file

```bash
cp fraud_generator/.env.example fraud_generator/.env   # if example exists
# or create manually — see Environment Variables section below
```

---

## Configuration

All configuration is done through environment variables (`.env` file or shell export).
Create a file at `fraud_generator/.env`:

```env
# LLM Backend — only "ollama" is supported in this version
LLM_BACKEND=ollama

# Ollama server URL (default: local)
OLLAMA_BASE_URL=http://localhost:11434

# Model to use for blueprint generation
PRIMARY_MODEL=llama3

# Timeout in seconds for a single Ollama response (raise on slow hardware)
OLLAMA_REQUEST_TIMEOUT=900

# Context window size — 4096 covers the full blueprint prompt
OLLAMA_NUM_CTX=4096

# LLM generation settings
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=4096

# Pipeline retries
MAX_BLUEPRINT_RETRIES=3

# Output directory for generated datasets
OUTPUT_DIR=output/synthetic_datasets

# Logging
LOG_LEVEL=INFO
LOG_FILE=fraud_generator.log
```

---

## Running the App

All commands are run from inside the `fraud_generator/` directory:

```bash
cd fraud_generator
```

### Streamlit Web UI

The recommended way to use FraudSynth. Provides a guided interface for selecting fraud category, describing your scenario, and downloading the dataset.

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

**Steps in the UI:**
1. **Select Fraud Category** — Card Fraud (EMVCo 3DS), UPI Fraud, or Other Fraud
2. **Describe Your Scenario** — plain English description or fill a structured form
3. Dataset is generated automatically and shown in a preview table
4. **Download** as CSV or JSON

**Example inputs:**
```
UPI collect scam, 500 rows, 15% fraud, amounts ₹200-₹1200, 7pm-11pm
```
```
BIN attack dataset, 50,000 transactions, 5% fraud, CSV
```
```
Money laundering via UPI, 10k rows, 33% fraud
```

---

### CLI — Interactive Mode

Launches a terminal-based session where you can describe multiple scenarios one after another.

```bash
python main.py
```

**Supported input formats inside the interactive prompt:**

```
# Plain English
Generate a UPI collect scam dataset with 500 rows, 15% fraud, CSV

# Labelled format
Fraud Scenario: Account Takeover
Rows: 20000
Fraud Ratio: 3%
Output Format: CSV

# Inline shorthand
Money Laundering, 5000, 33%, csv

# Built-in demo
demo
```

---

### CLI — One-liner Mode

Pass the scenario directly as a command-line argument:

```bash
python main.py --scenario "UPI collect scam, 500 rows, 15% fraud"

python main.py --scenario "BIN Attack, 100000, 5%, csv"

python main.py --scenario "Generate a money laundering dataset, 10k rows, 33% fraud, parquet"
```

---

### CLI — Demo Mode

Run a built-in preconfigured demo without describing anything:

```bash
python main.py --demo                       # BIN Attack (default)
python main.py --demo bin_attack
python main.py --demo card_testing
python main.py --demo account_takeover
python main.py --demo money_laundering
```

---

### CLI — Skip LLM (Blueprint Mode)

If you have already generated a blueprint JSON (or want to reproduce a dataset exactly), bypass the LLM entirely:

```bash
python main.py --blueprint output/synthetic_datasets/bin_attack_blueprint.json
```

This is useful for:
- Reproducing a previous dataset exactly (deterministic given the same blueprint)
- Sharing blueprints with colleagues so they can generate the same dataset
- Iterating on the blueprint manually without re-running the LLM

---

## Branch Guide

| Branch | Purpose |
|---|---|
| `main` | **Complete project — everything merged here.** Full dataset generator with Card (EMVCo 3DS), UPI, and Generic fraud engines + Streamlit UI. Start here. |
| `Rule_Engine` | **Rule Engine evaluation suite.** Upload a generated dataset, describe a fraud pattern, select detection rules, and view Precision / Recall / F1 metrics against ground-truth labels. |
| `HigherAudienceChanges2` | Pre-merge snapshot — UPI + Generic engines added. Superseded by `main`. |
| `HigherAudienceChanges` | Pre-merge snapshot — Streamlit UI improvements. Superseded by `main`. |
| `Agentic4` | Agentic v4 — LLM code generation mode (experimental). |
| `Agentic3` | Agentic v3 — first version with Streamlit UI. |
| `emvco-v1` | EMVCo 3DS card fraud engine — standalone, early version. |

---

### Using the Rule Engine (branch: `Rule_Engine`)

The Rule Engine branch adds a 4-step evaluation wizard on top of the dataset generator. Use it to measure how well a set of fraud detection rules fires on a generated dataset.

#### Checkout the branch

```bash
git checkout Rule_Engine
```

#### Install dependencies (same as main)

```bash
cd fraud_generator
pip install -r requirements.txt
```

#### Run the Rule Engine app

```bash
streamlit run app.py
```

#### Workflow

| Step | What you do |
|---|---|
| **1 — Upload Dataset** | Upload a CSV generated by FraudSynth (or any labelled transaction dataset with a `fraud_label` column) |
| **2 — Describe Pattern** | Describe the fraud pattern in plain English (e.g., *"UPI collect scam, ₹200–₹1200, 7pm–11pm, rapid requests"*) |
| **3 — Select Rules** | Choose or configure the detection rules you want to evaluate (velocity thresholds, amount ranges, VPA flags, etc.) |
| **4 — View Metrics** | See Precision, Recall, F1 Score, and Fraud Hit Rate — calculated against the ground-truth `fraud_label` column |

#### Understanding the metrics

| Metric | Meaning |
|---|---|
| **Flagged** | Number of transactions your rules fired on |
| **Fraud Captured** | How many actual fraud cases were caught (True Positives) |
| **Precision** | Of all flagged transactions, what fraction were real fraud |
| **Recall** | Of all real fraud transactions, what fraction were caught |
| **F1 Score** | Harmonic mean of Precision and Recall |
| **Fraud Hit Rate** | Percentage of fraud cases captured by the rules |

---

## Output Format

Generated datasets are saved in `fraud_generator/output/synthetic_datasets/`.

Two files are always produced per run:
- `<scenario_name>_synthetic_dataset.<format>` — the dataset (CSV / JSON / Parquet)
- `<scenario_name>_blueprint.json` — the quantitative blueprint used to generate it

### UPI Dataset Columns (key fields)

| Column | Type | Description |
|---|---|---|
| `txn_id` | str | 12-digit transaction reference |
| `timestamp` | datetime | Transaction time in IST |
| `hour_of_day` | int | 0–23 |
| `sender_vpa` / `receiver_vpa` | str | e.g. `rahul@okaxis` |
| `amount` | float | Transaction amount in ₹ |
| `txn_type` | str | `COLLECT_REQUEST` / `PUSH_PAY` / `QR_PAY` / `P2PM` |
| `txn_status` | str | `SUCCESS` / `FAILED` |
| `sender_velocity_1h` | int | Transactions sent in last 1 hour |
| `collect_requests_1h` | int | Collect requests received in last 1 hour |
| `is_new_vpa` | int | 1 if receiver VPA registered < 7 days ago |
| `is_first_txn_to_vpa` | int | 1 if first-ever transaction to this VPA |
| `failed_attempts_before` | int | Failed auth attempts in this session |
| `receiver_fraud_score` | float | Historical fraud risk score 0.0–1.0 |
| `fraud_label` | int | **Ground truth — 1 = fraud, 0 = legitimate** |
| `fraud_type` | str | e.g. `UPI Collect Scam`, `UPI Mule Transfer` |

### Card Dataset Columns (key fields)

Follows the EMVCo 3-D Secure v2.3.1 specification. Key fields include `threeds_server_trans_id`, `trans_status`, `eci`, `velocity_1h`, `new_device_flag`, `cross_border_flag`, `amount_vs_avg_ratio`, `fraud_label`, `fraud_pattern`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_BACKEND` | `ollama` | LLM backend to use |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `PRIMARY_MODEL` | `llama3.2:3b` | Model for blueprint generation |
| `OLLAMA_REQUEST_TIMEOUT` | `900` | Seconds before HTTP timeout — raise for slow hardware |
| `OLLAMA_NUM_CTX` | `4096` | Context window tokens for Ollama |
| `LLM_TEMPERATURE` | `0.2` | LLM generation temperature |
| `LLM_MAX_TOKENS` | `4096` | Max tokens per LLM response |
| `MAX_BLUEPRINT_RETRIES` | `3` | Retry attempts if blueprint is invalid |
| `OUTPUT_DIR` | `output/synthetic_datasets` | Where datasets are saved |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG` / `INFO` / `WARNING`) |
| `LOG_FILE` | `fraud_generator.log` | Log file path |

---

## Troubleshooting

**Ollama timeout during blueprint generation**

The LLM generating a blueprint JSON can take 5–15 minutes on CPU-only machines. If you see a timeout error:

```env
OLLAMA_REQUEST_TIMEOUT=1200
OLLAMA_NUM_CTX=4096
```

**`ConnectionRefusedError` when starting the app**

Ollama is not running. Start it:
```bash
ollama serve
```

**Blueprint validation keeps failing**

Increase retries and check your model is pulling a recent Llama 3 version:
```bash
ollama pull llama3
```
```env
MAX_BLUEPRINT_RETRIES=5
```

**Dataset has wrong row count or fraud ratio**

This is a known LLM behaviour — the blueprint generator always overrides LLM-written values with your exact input, so the final dataset will match what you specified.

**`ModuleNotFoundError` on import**

Make sure you are running from inside the `fraud_generator/` directory and your virtual environment is activated:
```bash
cd fraud_generator
source ../venv/bin/activate
```

---

## Notes

- All data is **100% synthetic** — no real transactions, no real PII
- Dataset generation is fully **deterministic** for a given blueprint + seed (default seed = 42)
- The LLM is used **only for blueprint creation** — the dataset itself is generated by a pure Python engine
- Blueprint JSON artifacts can be shared so teammates reproduce the exact same dataset without re-running the LLM

---

*FraudSynth — PayU Risk Intelligence*
