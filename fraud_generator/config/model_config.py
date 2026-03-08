"""
config/model_config.py
Model and system configuration for the Agentic Fraud Dataset Generator.
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
#   ollama pull llama2
#   ollama pull qwen2.5-coder:7b
AVAILABLE_MODELS = {
    "llama3": "llama3",
    "qwen2.5-coder": "qwen2.5-coder:7b",
}

# Primary model for blueprint & scenario interpretation
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "llama3")

# Model used for code generation & error fixing
CODE_MODEL = os.getenv("CODE_MODEL", "qwen2.5-coder")

# ─── Generation Parameters ───────────────────────────────────────────────────
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# ─── Pipeline Settings ───────────────────────────────────────────────────────
MAX_BLUEPRINT_RETRIES = int(os.getenv("MAX_BLUEPRINT_RETRIES", "3"))
MAX_CODE_RETRIES = int(os.getenv("MAX_CODE_RETRIES", "5"))
CODE_EXECUTION_TIMEOUT = int(os.getenv("CODE_EXECUTION_TIMEOUT", "420"))  # seconds

# ─── Output ──────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "output/synthetic_datasets")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "fraud_generator.log")
