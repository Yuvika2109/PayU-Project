"""
config/model_config.py  (v3)
Model and system configuration for the Agentic Fraud Dataset Generator.

v3 additions: OLLAMA_REQUEST_TIMEOUT and OLLAMA_NUM_CTX
  — fix Ollama read-timeout on the large blueprint generation prompt.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── LLM Backend ─────────────────────────────────────────────────────────────
# Supported backends: "ollama" | "openai_compatible"
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")

# ─── Ollama Settings ──────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Available models (must be pulled in Ollama first):
#   ollama pull llama3
#   ollama pull qwen2.5-coder:7b
AVAILABLE_MODELS = {
    "llama3":        "llama3",
    "qwen2.5-coder": "qwen2.5-coder:7b",
}

# Primary model for blueprint & scenario interpretation
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "llama3.2:3b")

# Model used for code generation & error fixing
CODE_MODEL = os.getenv("CODE_MODEL", "qwen2.5-coder")

# ─── Ollama Performance Tuning (NEW in v3) ────────────────────────────────────
# OLLAMA_REQUEST_TIMEOUT
#   Seconds to wait for a single Ollama HTTP response.
#   The blueprint prompt is ~7800 chars; llama3 on a mid-range GPU can take
#   8–12 minutes to produce the full JSON.  Default raised from 300 → 900 s.
#   Raise further (e.g. 1200) if you still see timeouts on slower hardware.
OLLAMA_REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", "900"))

# OLLAMA_NUM_CTX
#   KV-cache context window size sent to Ollama.
#   Without this, Ollama may default to 32k+ tokens, which dramatically
#   increases memory allocation and time-to-first-token on modest hardware.
#   4096 covers the full blueprint prompt with room to spare.
#   Raise to 8192 only if you see blueprint JSON responses getting cut off.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

# ─── Generation Parameters ───────────────────────────────────────────────────
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS  = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# ─── Pipeline Settings ───────────────────────────────────────────────────────
MAX_BLUEPRINT_RETRIES  = int(os.getenv("MAX_BLUEPRINT_RETRIES", "3"))
MAX_CODE_RETRIES       = int(os.getenv("MAX_CODE_RETRIES", "5"))
CODE_EXECUTION_TIMEOUT = int(os.getenv("CODE_EXECUTION_TIMEOUT", "420"))  # seconds

# ─── Output ──────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output/synthetic_datasets")
LOG_LEVEL  = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE   = os.getenv("LOG_FILE", "fraud_generator.log")