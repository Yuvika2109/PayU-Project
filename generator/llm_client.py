

import json
import re
import requests


# ── Ollama config ─────────────────────────────────────────────────────────────

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

MAX_RETRIES  = 3
TIMEOUT_SECS = 120  # blueprint is small — 2 min is generous


# ── Default blueprint (fallback if LLM fails completely) ─────────────────────

DEFAULT_BLUEPRINT = {
    "amount_min":          0.50,
    "amount_max":          10.00,
    "amount_distribution": "uniform",
    "velocity_per_card":   50,
    "time_window_hours":   2,
    "num_unique_cards":    15,
    "shared_bin":          True,
    "bin_prefix":          "453201",
    "merchants":           ["Amazon", "Steam", "Spotify"],
    "merchant_categories": ["streaming", "gaming"],
    "countries":           ["US", "IN"],
    "devices":             ["mobile", "desktop"],
    "time_clustering":     "burst",
}

# Every field that must exist and its expected type
_REQUIRED_FIELDS = {
    "amount_min":          (int, float),
    "amount_max":          (int, float),
    "amount_distribution": str,
    "velocity_per_card":   (int, float),
    "time_window_hours":   (int, float),
    "num_unique_cards":    (int, float),
    "shared_bin":          bool,
    "bin_prefix":          str,
    "merchants":           list,
    "countries":           list,
    "devices":             list,
    "time_clustering":     str,
}


# ── Raw API call (streaming) ──────────────────────────────────────────────────

def _call_ollama(prompt: str) -> str:
    """Sends prompt to Ollama with streaming to prevent timeouts."""
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
    }

    try:
        response = requests.post(
            OLLAMA_URL, json=payload, timeout=TIMEOUT_SECS, stream=True,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot reach Ollama. Make sure it is running — "
            "open a terminal and run: ollama serve"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Ollama timed out after {TIMEOUT_SECS}s.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Ollama HTTP error: {e}")

    full_text = ""
    for raw_line in response.iter_lines():
        if raw_line:
            try:
                chunk = json.loads(raw_line)
                full_text += chunk.get("response", "")
                if chunk.get("done", False):
                    break
            except json.JSONDecodeError:
                continue

    return full_text


# ── JSON extractor ────────────────────────────────────────────────────────────

def _extract_json_object(raw_text: str) -> dict:
    """Extracts a JSON object (not array) from the LLM response."""

    # Strategy 1: code block ```json { ... } ```
    code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 2: first { ... } in the text
    obj_match = re.search(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", raw_text, re.DOTALL)
    if obj_match:
        try:
            return json.loads(obj_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: entire response is valid JSON
    try:
        parsed = json.loads(raw_text.strip())
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    raise ValueError(
        "Could not extract a valid JSON object from LLM response.\n"
        f"Raw (first 500 chars): {raw_text[:500]}"
    )


# ── Blueprint validator ───────────────────────────────────────────────────────

def _validate_blueprint(bp: dict) -> dict:
    """
    Validates the LLM blueprint and fills in defaults for any missing or
    wrongly-typed fields. Never crashes — always returns a usable blueprint.
    """
    clean = {}

    for field, expected_type in _REQUIRED_FIELDS.items():
        value = bp.get(field)

        # Field present and correct type → keep it
        if value is not None and isinstance(value, expected_type):
            clean[field] = value
        # Field present but wrong type → try to coerce
        elif value is not None:
            try:
                if expected_type in ((int, float), float):
                    clean[field] = float(value)
                elif expected_type == str:
                    clean[field] = str(value)
                elif expected_type == bool:
                    clean[field] = bool(value)
                elif expected_type == list and isinstance(value, str):
                    clean[field] = [value]
                else:
                    clean[field] = DEFAULT_BLUEPRINT[field]
            except (ValueError, TypeError):
                clean[field] = DEFAULT_BLUEPRINT[field]
                print(f"[llm_client] Field '{field}' had bad value, using default.")
        # Field missing → use default
        else:
            clean[field] = DEFAULT_BLUEPRINT[field]
            print(f"[llm_client] Field '{field}' missing from LLM output, using default.")

    # Ensure numeric sanity
    clean["amount_min"]       = max(0.01, float(clean["amount_min"]))
    clean["amount_max"]       = max(clean["amount_min"] + 0.01, float(clean["amount_max"]))
    clean["velocity_per_card"] = max(1, int(clean["velocity_per_card"]))
    clean["time_window_hours"] = max(1, int(clean["time_window_hours"]))
    clean["num_unique_cards"]  = max(1, int(clean["num_unique_cards"]))

    # Ensure bin_prefix is 6 digits
    bp_bin = str(clean["bin_prefix"]).replace(" ", "").replace("-", "")
    if not bp_bin.isdigit() or len(bp_bin) < 6:
        bp_bin = "453201"
    clean["bin_prefix"] = bp_bin[:6]

    # Ensure lists are non-empty
    if not clean["merchants"]:
        clean["merchants"] = DEFAULT_BLUEPRINT["merchants"]
    if not clean["countries"]:
        clean["countries"] = DEFAULT_BLUEPRINT["countries"]
    if not clean["devices"]:
        clean["devices"] = DEFAULT_BLUEPRINT["devices"]

    return clean


# ── Public interface ──────────────────────────────────────────────────────────

def get_fraud_blueprint(prompt: str) -> dict:
    """
    Calls Ollama once and returns a validated fraud blueprint dict.

    Falls back to DEFAULT_BLUEPRINT if all retries fail — the system
    never crashes, it just uses sensible defaults and logs a warning.

    Parameters
    ----------
    prompt : complete prompt from prompt_builder.build_prompt()

    Returns
    -------
    dict — validated blueprint with all required fields
    """
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[llm_client] Calling Ollama (attempt {attempt}/{MAX_RETRIES})...")
            raw_text  = _call_ollama(prompt)
            raw_bp    = _extract_json_object(raw_text)
            blueprint = _validate_blueprint(raw_bp)
            print(f"[llm_client] Blueprint received and validated.")
            return blueprint

        except (RuntimeError, ValueError) as e:
            last_error = e
            print(f"[llm_client] Attempt {attempt} failed: {e}")

    # All retries failed — use default blueprint
    print(
        f"[llm_client] WARNING: All {MAX_RETRIES} attempts failed. "
        f"Last error: {last_error}\n"
        f"[llm_client] Using DEFAULT_BLUEPRINT as fallback."
    )
    return DEFAULT_BLUEPRINT.copy()


