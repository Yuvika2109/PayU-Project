import json
import re
import requests
from typing import Any


# ── Ollama config ─────────────────────────────────────────────────────────────

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

MAX_RETRIES  = 3    # retries per batch if JSON extraction fails
TIMEOUT_SECS = 300  # 5 min — raised because Llama 3 is slow on CPU
BATCH_SIZE   = 5    # rows requested per LLM call — keep this small (5–10)


# ── Raw API call (streaming) ──────────────────────────────────────────────────

def _call_ollama(prompt: str) -> str:
    """
    Sends a prompt to Ollama using streaming mode so the connection stays
    alive while tokens are generated — this prevents read timeouts on slow
    machines. Assembles all streamed chunks into a single string.
    """
    payload = {
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,   # streaming keeps the socket alive token-by-token
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=TIMEOUT_SECS,
            stream=True,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "Cannot reach Ollama. Make sure it is running — open a terminal and run: ollama serve"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"Ollama timed out after {TIMEOUT_SECS}s even with streaming. "
            "Try lowering BATCH_SIZE in llm_client.py, or run: ollama pull llama3:8b"
        )
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"Ollama returned an HTTP error: {e}")

    # Each streamed line is a JSON object: {"response": "token", "done": false}
    full_text = ""
    for raw_line in response.iter_lines():
        if raw_line:
            try:
                chunk = json.loads(raw_line)
                full_text += chunk.get("response", "")
                if chunk.get("done", False):
                    break
            except json.JSONDecodeError:
                continue  # skip any malformed lines

    return full_text


# ── JSON extractor ────────────────────────────────────────────────────────────

def _extract_json_from_response(raw_text: str) -> list[dict]:
    """
    Extracts a JSON array from the LLM's raw text.
    Handles markdown code fences, leading prose, and wrapped objects.
    """
    # Strategy 1: markdown code block ```json [...] ```
    code_block_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw_text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 2: first [ ... ] span anywhere in the text
    array_match = re.search(r"(\[.*\])", raw_text, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: entire response is valid JSON
    try:
        parsed = json.loads(raw_text.strip())
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for value in parsed.values():
                if isinstance(value, list):
                    return value
    except json.JSONDecodeError:
        pass

    raise ValueError(
        "Could not extract a valid JSON array from the LLM response.\n"
        f"Raw response (first 500 chars):\n{raw_text[:500]}"
    )


# ── Public interface ──────────────────────────────────────────────────────────

def generate_fraud_transactions(prompt: str, total_needed: int = None) -> list[dict[str, Any]]:
    """
    Calls Ollama in small batches (BATCH_SIZE rows each) and accumulates
    results until enough rows are collected.

    Why batching?
      Asking for 20+ rows in one shot makes the LLM take 2-3 minutes and
      often times out. Asking for 5 rows at a time is fast (~15-20s each)
      and much more reliable.

    Parameters
    ----------
    prompt       : base prompt from prompt_builder — batch count is appended
    total_needed : how many fraud rows to collect in total.
                   If None, runs exactly one batch of BATCH_SIZE.

    Returns
    -------
    list of dicts — one per transaction (unvalidated; data_builder validates)
    """
    if total_needed is None:
        total_needed = BATCH_SIZE

    all_rows   = []
    batch_num  = 0

    while len(all_rows) < total_needed:
        batch_num += 1
        remaining  = total_needed - len(all_rows)
        this_batch = min(BATCH_SIZE, remaining)

        # Append the batch count to the prompt so the LLM knows exactly how many to produce
        batch_prompt = prompt + f"\n\nGenerate exactly {this_batch} transactions in this batch."

        print(f"[llm_client] Batch {batch_num} — requesting {this_batch} rows "
              f"({len(all_rows)}/{total_needed} collected so far)...")

        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw_text = _call_ollama(batch_prompt)
                rows     = _extract_json_from_response(raw_text)
                all_rows.extend(rows)
                print(f"[llm_client] Batch {batch_num} OK — got {len(rows)} rows.")
                break  # move to next batch
            except (RuntimeError, ValueError) as e:
                print(f"[llm_client] Batch {batch_num}, attempt {attempt}/{MAX_RETRIES} failed: {e}")
                last_error = e
                if attempt == MAX_RETRIES:
                    raise RuntimeError(
                        f"Batch {batch_num} failed after {MAX_RETRIES} attempts. "
                        f"Last error: {last_error}"
                    )

    print(f"[llm_client] Done — collected {len(all_rows)} fraud rows total.")
    return all_rows[:total_needed]  # trim any extras from the last batch


