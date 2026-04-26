# 🛡️ Fraud Rule Engine

An end-to-end, **LLM-powered fraud detection rule engine** that runs entirely on your local machine using [Ollama](https://ollama.com). Upload a dataset, describe a fraud pattern in plain English, get AI-generated detection rules, select the ones you want, and get full precision/recall/F1 metrics — all without sending data to any external API.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (React UI)                       │
│  Step 1: Upload CSV → Step 2: Describe Fraud → Step 3: Select   │
│                    Rules → Step 4: View Metrics                  │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP/REST
┌─────────────────────────▼───────────────────────────────────────┐
│                   FastAPI Backend (Python)                        │
│  POST /api/v1/upload           → ingest CSV, detect schema       │
│  POST /api/v1/rules/generate   → LLM → structured FraudRules    │
│  POST /api/v1/rules/evaluate   → pandas evaluation + metrics     │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP (JSON)
┌─────────────────────────▼───────────────────────────────────────┐
│                   Ollama (Local LLM)                              │
│  ollama serve  · any instruction-tuned model                      │
│  Recommended: llama3.2:3b · llama3:8b · mistral:7b              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

- **4-step wizard UI** — Upload → Generate → Select → Metrics
- **Schema auto-detection** — EMVCo card transactions or EMVCo 3DS
- **LLM rule generation** — structured JSON rules with conditions, severity, category, tags
- **Manual rule selection** — filter by severity / category, expand to inspect conditions
- **Full metrics dashboard** — Precision, Recall, F1, flag rate, per-rule and aggregate
- **Interactive charts** — bar charts, radar chart, flagged sample table
- **Export** — download evaluation results as JSON
- **100% local** — no OpenAI / external API calls; Ollama only

---

## Quick Start

### 1. Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | ≥ 3.11 | [python.org](https://python.org) |
| Node.js | ≥ 20 | [nodejs.org](https://nodejs.org) |
| Ollama | latest | [ollama.com](https://ollama.com) |

### 2. Pull a model

```bash
# Lightweight (recommended for most machines)
ollama pull llama3.2:3b

# Higher quality (needs ~8 GB RAM)
ollama pull llama3:8b-instruct

# Best quality (needs ~40 GB RAM)
ollama pull llama3:70b-instruct

# MoE option
ollama pull mixtral:8x7b-instruct
```

### 3. Start Ollama

```bash
ollama serve
```

### 4. Start the backend

```bash
cd backend

# Copy environment config
cp .env.example .env
# Edit OLLAMA_MODEL= to match what you pulled

pip install -r requirements.txt

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Start the frontend

```bash
cd frontend

npm install
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## Docker Compose (Full Stack)

```bash
# Make sure Ollama is running locally first: ollama serve
# Edit OLLAMA_MODEL in docker-compose.yml or .env

docker compose up --build
```

- Frontend → http://localhost:3000
- Backend API → http://localhost:8000
- Swagger docs → http://localhost:8000/docs

---

## Supported Dataset Schemas

### EMVCo Card Transaction
Classic payment transaction dataset.

Key columns: `transaction_id`, `card_number`, `bin_number`, `transaction_amount`, `merchant_category`, `foreign_ip_flag`, `hour_of_day`, `is_weekend`, `user_id`, `merchant_id`, `device_id`, `fraud_label`

### EMVCo 3DS (3-D Secure)
Card-not-present / authentication / money-laundering dataset.

Key columns: `threeds_server_trans_id`, `acs_trans_id`, `acct_number`, `purchase_amount`, `velocity_1h`, `velocity_24h`, `amount_vs_avg_ratio`, `cross_border_flag`, `new_device_flag`, `new_shipping_addr_flag`, `high_risk_mcc_flag`, `fraud_label`

> **Note:** If your dataset does not have a `fraud_label` column, precision/recall will show 0 but flag rate and rule logic still work correctly.

---

## Project Structure

```
fraud-rule-engine/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py          # FastAPI routes
│   │   ├── core/
│   │   │   ├── config.py          # Settings via pydantic-settings
│   │   │   ├── llm_client.py      # Ollama HTTP client
│   │   │   └── schema_detector.py # CSV schema auto-detection
│   │   ├── models/
│   │   │   └── schemas.py         # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── dataset_service.py # CSV upload, parquet session cache
│   │   │   ├── evaluator.py       # Pandas rule evaluation + metrics
│   │   │   └── rule_generator.py  # LLM prompt builder + parser
│   │   └── main.py                # FastAPI app + CORS
│   ├── .env.example
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   └── Layout.tsx     # Shell with step nav + header
│   │   │   ├── steps/
│   │   │   │   ├── UploadStep.tsx   # Step 1: drag-drop CSV upload
│   │   │   │   ├── GenerateStep.tsx # Step 2: scenario + LLM call
│   │   │   │   ├── SelectRulesStep.tsx # Step 3: rule picker
│   │   │   │   └── MetricsStep.tsx  # Step 4: charts + table
│   │   │   └── ui/
│   │   │       ├── ScoreRing.tsx    # Radial progress rings
│   │   │       ├── Skeleton.tsx     # Loading skeletons
│   │   │       └── StepIndicator.tsx # Progress bar
│   │   ├── lib/
│   │   │   ├── api.ts             # Axios API client
│   │   │   ├── store.ts           # Zustand global state
│   │   │   └── utils.ts           # Formatters + helpers
│   │   ├── types/
│   │   │   └── index.ts           # TypeScript types (mirrors backend schemas)
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css              # Tailwind + design system CSS vars
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
│
├── docker-compose.yml
└── README.md
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/upload` | POST | Upload CSV, get `session_id` |
| `/api/v1/rules/generate` | POST | Generate rules from scenario |
| `/api/v1/rules/evaluate/{session_id}` | POST | Evaluate selected rules |
| `/api/v1/sessions/{session_id}` | GET | Get session metadata |
| `/api/v1/sessions/{session_id}` | DELETE | Delete session |
| `/api/v1/health` | GET | LLM + service health check |

Full interactive docs: **http://localhost:8000/docs**

---

## Configuration

Edit `backend/.env`:

```env
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b      # change to your pulled model
OLLAMA_TIMEOUT=180             # seconds; increase for large models
OLLAMA_MAX_TOKENS=4096

# App
MAX_UPLOAD_MB=100
SESSION_DIR=/tmp/fraud_sessions
```

---

## Rule Structure

Each generated rule contains:

```json
{
  "id": "R001",
  "name": "Micro-Transaction Velocity Burst",
  "description": "Detects card testing via rapid low-value probes",
  "category": "velocity",
  "severity": "high",
  "logic_expression": "transaction_amount < 5 AND velocity_24h > 10",
  "match_any": false,
  "tags": ["card-testing", "velocity", "micro-transaction"],
  "conditions": [
    { "field": "transaction_amount", "operator": "lt", "value": 5, "description": "Low value probe" },
    { "field": "velocity_24h", "operator": "gt", "value": 10, "description": "High 24h transaction count" }
  ]
}
```

---

## Troubleshooting

**Ollama not connecting**
```bash
ollama serve   # must be running
curl http://localhost:11434/api/tags  # should list models
```

**Model not generating valid JSON**
- Try a larger model: `llama3:8b-instruct` produces more reliable structured output
- Increase `OLLAMA_TIMEOUT` if the model is slow

**Upload fails**
- Ensure the file is UTF-8 encoded CSV
- Check MAX_UPLOAD_MB in `.env`

**Precision/Recall are 0**
- Your dataset needs a `fraud_label` column with values 0 (legitimate) and 1 (fraud)

---

## License

MIT
