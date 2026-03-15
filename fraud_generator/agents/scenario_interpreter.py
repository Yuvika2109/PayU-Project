"""
agents/scenario_interpreter.py  (v3)
Converts free-text user input into a structured scenario parameter dict.

Supports THREE input modes — tried in order:

  1. Labelled (multi-line)  ── detected by label:value patterns
       Fraud Scenario: Money Laundering
       Rows: 5000
       Fraud Ratio: 33%
       Output Format: CSV

  2. Inline (comma-separated)  ── short comma-split tokens, no sentence structure
       Money Laundering, 5000, 33%, csv

  3. Natural-language sentence  ── anything that doesn't match above (NEW)
       "Generate a BIN attack dataset with 50,000 transactions,
        around 7% fraud, and save it as parquet."

       "I need card testing fraud data — 20k rows, 10 percent fraud
        rate, CSV format please."

       "Create money laundering data. Use 5000 rows with a one-third
        fraud ratio. Output should be JSON."
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from utils.logger import get_logger

logger = get_logger("agents.scenario_interpreter")

# ─── Known Fraud Scenarios ────────────────────────────────────────────────────
KNOWN_SCENARIOS: Dict[str, Dict[str, str]] = {
    "bin attack": {
        "fraud_type": "Card-Not-Present Fraud",
        "description": (
            "Attacker systematically tests BIN ranges with small transactions "
            "to identify valid card numbers before large-scale fraud."
        ),
    },
    "card testing": {
        "fraud_type": "Card-Not-Present Fraud",
        "description": (
            "Small test transactions are made to verify stolen card credentials "
            "before using them for larger purchases."
        ),
    },
    "account takeover": {
        "fraud_type": "Identity Fraud",
        "description": (
            "Fraudster gains access to a legitimate account and changes credentials "
            "before conducting fraudulent transactions."
        ),
    },
    "money laundering": {
        "fraud_type": "Financial Crime",
        "description": (
            "Illicit funds are passed through multiple transactions to obscure their "
            "origin and appear as legitimate income."
        ),
    },
    "refund fraud": {
        "fraud_type": "Return / Refund Abuse",
        "description": (
            "Fraudster exploits refund policies by falsely claiming non-receipt "
            "or returning counterfeit / different items."
        ),
    },
    "identity fraud": {
        "fraud_type": "Identity Theft",
        "description": (
            "Stolen personal information is used to open new accounts or conduct "
            "transactions without the victim's knowledge."
        ),
    },
    "phishing": {
        "fraud_type": "Social Engineering",
        "description": (
            "Deceptive communications trick victims into revealing credentials or "
            "authorising fraudulent transfers."
        ),
    },
    "synthetic identity": {
        "fraud_type": "Identity Fraud",
        "description": (
            "Fraudster combines real and fabricated PII to create new identities "
            "for credit and transaction abuse."
        ),
    },
    "friendly fraud": {
        "fraud_type": "Chargeback Fraud",
        "description": (
            "Legitimate cardholder disputes a valid transaction to obtain a refund "
            "while keeping the goods or services."
        ),
    },
    "triangulation fraud": {
        "fraud_type": "E-commerce Fraud",
        "description": (
            "Fraudster sets up a fake storefront, collects payment, then uses stolen "
            "cards to fulfil orders, leaving victims with fraudulent charges."
        ),
    },
}

_DEFAULT_SCENARIO = {
    "fraud_type": "Generic Fraud",
    "description": "Custom fraud scenario as described by the user.",
}

# ─── Output Format Aliases ────────────────────────────────────────────────────
_FORMAT_MAP: Dict[str, str] = {
    "csv":     "csv",
    "json":    "json",
    "parquet": "parquet",
    "excel":   "excel",
    "xlsx":    "excel",
    "xls":     "excel",
}

_NUMERIC_LIKE = re.compile(r"^[\d,_%.\s]+$")


# ─── NLP Extractor (new in v3) ────────────────────────────────────────────────

class NLPScenarioExtractor:
    """
    Uses the LLM to extract structured fields from a free-form sentence.

    Asks the LLM to return a small JSON object with exactly four keys:
        scenario_name, rows, fraud_ratio, output_format

    Any field the LLM cannot determine is returned as null; downstream
    _fill_defaults() substitutes sensible values for anything missing.
    """

    _PROMPT = """\
You are a data extraction assistant. Extract fraud dataset parameters from the user's request.

Return ONLY a valid JSON object with exactly these four keys:
  "scenario_name"  : string  — the fraud scenario type (e.g. "BIN Attack", "Money Laundering")
  "rows"           : integer — total number of rows/transactions requested, or null if not stated
  "fraud_ratio"    : float   — fraud ratio as a decimal between 0 and 1, or null if not stated
                               (convert percentages: "10%" → 0.10, "one-third" → 0.33)
  "output_format"  : string  — one of: csv, json, parquet, excel — or null if not stated

Rules:
- "k" or "thousand" after a number means ×1000  (e.g. "50k" → 50000, "20 thousand" → 20000).
- "million" or "M" means ×1000000.
- Written numbers: "twenty thousand" → 20000, "half a million" → 500000.
- Fraud ratio: "10%", "10 percent", "one-third" → 0.33, "a third" → 0.33, "one in ten" → 0.10.
- Normalise scenario names (e.g. "card testing attack" → "Card Testing").
- If a field is genuinely absent, return null — do NOT guess.
- Return ONLY the JSON object — no markdown, no explanation.

User request:
{user_input}
"""

    def extract(self, raw_input: str) -> Dict[str, Any]:
        """
        Send raw_input to the LLM and return a partial params dict.
        Falls back to an empty dict on any LLM or parse error so the
        caller's regex fallback + defaults can still fill in the gaps.
        """
        try:
            from core.llm_interface import generate_response
            from utils.json_parser import extract_json

            prompt = self._PROMPT.format(user_input=raw_input.strip())
            logger.debug("NLP extractor prompt (%d chars)", len(prompt))

            raw = generate_response(prompt, temperature=0.0, max_tokens=256)
            logger.debug("NLP extractor raw response: %.300s", raw)

            parsed = extract_json(raw)
            if not isinstance(parsed, dict):
                logger.warning("NLP extractor: non-dict response (%s)", type(parsed))
                return {}

            params: Dict[str, Any] = {}

            sn = parsed.get("scenario_name")
            if isinstance(sn, str) and sn.strip():
                params["scenario_name"] = sn.strip()

            rows = parsed.get("rows")
            if isinstance(rows, (int, float)) and rows and rows > 0:
                params["rows"] = int(rows)

            ratio = parsed.get("fraud_ratio")
            if isinstance(ratio, (int, float)) and ratio is not None:
                r = float(ratio)
                if r > 1.0:          # LLM accidentally returned e.g. 10 instead of 0.10
                    r = r / 100.0
                params["fraud_ratio"] = round(r, 4)

            fmt = parsed.get("output_format")
            if isinstance(fmt, str) and fmt.strip():
                params["output_format"] = _FORMAT_MAP.get(
                    fmt.lower().strip(), fmt.lower().strip()
                )

            logger.info("NLP extractor result: %s", params)
            return params

        except Exception as exc:   # noqa: BLE001
            logger.warning("NLP extractor failed (%s) — regex fallback will run.", exc)
            return {}


# ─── Main Interpreter Agent ───────────────────────────────────────────────────

class ScenarioInterpreterAgent:
    """
    Parse raw user input into a normalised scenario parameter dict.

    Detection order:
      1. Labelled  (label:value pairs present)  → _parse_labelled
      2. Positional (comma-separated, short tokens, no sentence structure) → _parse_positional
      3. Natural language sentence → NLPScenarioExtractor + regex safety-net

    Output schema::

        {
            "scenario_name": str,
            "fraud_type":    str,
            "description":   str,
            "rows":          int,
            "fraud_ratio":   float,   # 0.0 – 1.0
            "output_format": str,     # "csv" | "json" | "parquet" | "excel"
        }
    """

    def __init__(self):
        self._nlp = NLPScenarioExtractor()

    def interpret(self, raw_input: str) -> Dict[str, Any]:
        """Main entry point. Accepts labelled, inline, or natural-language input."""
        logger.info("Interpreting scenario input (%d chars)", len(raw_input))
        text = raw_input.strip()

        # ── Choose parsing strategy ───────────────────────────────────────────
        if self._looks_labelled(text):
            logger.info("Input mode: LABELLED")
            params = self._parse_labelled(text)

        elif self._looks_positional(text):
            logger.info("Input mode: POSITIONAL")
            params = self._parse_positional(text)

        else:
            logger.info("Input mode: NATURAL LANGUAGE — invoking NLP extractor")
            params = self._nlp.extract(text)

            # Regex safety-net: fill anything the LLM missed
            fallback = self._regex_number_fallback(text)
            for k, v in fallback.items():
                params.setdefault(k, v)

            # Last-resort scenario name: scan sentence for known keywords
            if not params.get("scenario_name"):
                params["scenario_name"] = self._scenario_from_sentence(text) or ""

        self._fill_defaults(params)
        self._enrich_scenario(params)

        logger.info(
            "Interpreted scenario: name='%s'  rows=%d  ratio=%.2f%%  format=%s",
            params["scenario_name"],
            params["rows"],
            params["fraud_ratio"] * 100,
            params["output_format"],
        )
        return params

    # ─── Input-Mode Detection ─────────────────────────────────────────────────

    @staticmethod
    def _looks_labelled(text: str) -> bool:
        """True when text contains explicit label:value pairs."""
        label_pattern = re.compile(
            r"(?:fraud[\s_-]?scenario|scenario|name|rows?|total[\s_-]?rows?"
            r"|count|size|fraud[\s_-]?ratio|ratio|rate|output[\s_-]?format|format)\s*[:\-=]",
            re.IGNORECASE,
        )
        return bool(label_pattern.search(text))

    @staticmethod
    def _looks_positional(text: str) -> bool:
        """
        True for short comma-separated lists like 'Money Laundering, 5000, 33%, csv'.
        A positional input:
          - has no newlines (multi-line → labelled)
          - splits into 2–6 comma-separated parts
          - every part is a short token (≤ 3 words) — not a sentence fragment
            (> 3 words per part signals written numbers / natural language phrases
             like "half a million rows" or "one third fraud rate")
        """
        if "\n" in text:
            return False
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if len(parts) < 2:
            return False
        return all(len(p.split()) <= 3 for p in parts)

    # ─── Labelled Parser (unchanged from v2) ─────────────────────────────────

    def _parse_labelled(self, text: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        params["scenario_name"] = self._extract_str(
            text, r"(?:fraud[\s_-]?scenario|scenario|name)\s*[:\-=]\s*(.+)"
        )
        params["rows"] = self._extract_int(
            text, r"(?:rows?|total[\s_-]?rows?|count|size)\s*[:\-=]\s*([\d,_]+)"
        )
        params["fraud_ratio"] = self._extract_ratio(
            text,
            r"(?:fraud[\s_-]?ratio|ratio|fraud[\s_-]?rate|rate)\s*[:\-=]\s*([\d.]+\s*%?)",
        )
        params["output_format"] = self._extract_format(
            text, r"(?:output[\s_-]?format|format|output)\s*[:\-=]\s*(\w+)"
        )
        return {k: v for k, v in params.items() if v is not None}

    # ─── Positional Parser (unchanged from v2) ────────────────────────────────

    def _parse_positional(self, text: str) -> Dict[str, Any]:
        """Parse: 'Money Laundering, 5000, 33%, csv'"""
        raw_parts = re.split(r"[,\n]+", text)
        parts = [p.strip() for p in raw_parts if p.strip()]

        params: Dict[str, Any] = {}

        # Pass 1: collect scenario name tokens (leading non-numeric parts)
        name_tokens: list = []
        remaining_start = 0

        for i, part in enumerate(parts):
            looks_int    = bool(re.match(r"^[\d,_]+$", part))
            looks_ratio  = bool(re.search(r"\d.*%", part))
            looks_float  = bool(re.match(r"^0?\.\d+$", part))
            looks_format = part.lower() in _FORMAT_MAP

            if looks_int or looks_ratio or looks_float or looks_format:
                remaining_start = i
                break
            else:
                name_tokens.append(part)
                remaining_start = i + 1

        if name_tokens:
            params["scenario_name"] = " ".join(name_tokens)

        # Pass 2: parse numeric/format tokens
        for part in parts[remaining_start:]:
            if re.search(r"\d.*%", part) and "fraud_ratio" not in params:
                ratio = self._parse_ratio(part)
                if ratio is not None:
                    params["fraud_ratio"] = ratio
                continue

            if re.match(r"^0\.\d+$", part) and "fraud_ratio" not in params:
                try:
                    params["fraud_ratio"] = float(part)
                except ValueError:
                    pass
                continue

            if part.lower() in _FORMAT_MAP and "output_format" not in params:
                params["output_format"] = _FORMAT_MAP[part.lower()]
                continue

            if re.match(r"^[\d,_]+$", part) and "rows" not in params:
                val = self._parse_int(part)
                if val is not None:
                    params["rows"] = val
                continue

        return {k: v for k, v in params.items() if v is not None}

    # ─── NL Helpers (new in v3) ───────────────────────────────────────────────

    def _regex_number_fallback(self, text: str) -> Dict[str, Any]:
        """
        Lightweight regex pass over free-text to catch numbers/ratios/formats
        the LLM may have missed. Never overwrites fields already extracted.
        """
        params: Dict[str, Any] = {}

        # Rows — various natural forms
        row_patterns = [
            (r"(\d[\d,]*)\s*k\b",                                             1_000),
            (r"(\d[\d,]*)\s*(?:thousand)\b",                                  1_000),
            (r"(\d[\d,]*)\s*(?:million|M)\b",                             1_000_000),
            (r"(\d[\d,]*)\s*(?:rows?|transactions?|records?|samples?|entries)", 1),
        ]
        for pat, multiplier in row_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m and "rows" not in params:
                try:
                    params["rows"] = int(m.group(1).replace(",", "")) * multiplier
                except ValueError:
                    pass
                break

        # Fraud ratio — percent or decimal
        for pat in [r"(\d+(?:\.\d+)?)\s*(?:%|percent(?:age)?)", r"\b(0\.\d+)\b"]:
            m = re.search(pat, text, re.IGNORECASE)
            if m and "fraud_ratio" not in params:
                r = self._parse_ratio(m.group(0))
                if r is not None:
                    params["fraud_ratio"] = r
                break

        # Output format keyword anywhere in the sentence
        for fmt_key in _FORMAT_MAP:
            if re.search(r"\b" + fmt_key + r"\b", text, re.IGNORECASE):
                params.setdefault("output_format", _FORMAT_MAP[fmt_key])
                break

        return {k: v for k, v in params.items() if v is not None}

    def _scenario_from_sentence(self, text: str) -> Optional[str]:
        """Scan the sentence for a known scenario keyword. Returns Title Case or None."""
        lower = text.lower()
        for key in sorted(KNOWN_SCENARIOS, key=len, reverse=True):
            if key in lower:
                return key.title()
        return None

    # ─── Field Helpers (unchanged from v2) ───────────────────────────────────

    def _extract_str(self, text: str, pattern: str) -> Optional[str]:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def _extract_int(self, text: str, pattern: str) -> Optional[int]:
        m = re.search(pattern, text, re.IGNORECASE)
        return self._parse_int(m.group(1)) if m else None

    def _extract_ratio(self, text: str, pattern: str) -> Optional[float]:
        m = re.search(pattern, text, re.IGNORECASE)
        return self._parse_ratio(m.group(1)) if m else None

    def _extract_format(self, text: str, pattern: str) -> Optional[str]:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return None
        raw = m.group(1).strip().lower()
        return _FORMAT_MAP.get(raw, raw)

    @staticmethod
    def _parse_int(s: str) -> Optional[int]:
        try:
            return int(re.sub(r"[,_\s]", "", s))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_ratio(s: str) -> Optional[float]:
        s = s.strip()
        try:
            val = float(re.sub(r"[%\s]", "", s))
            return val / 100.0 if val > 1.0 else val
        except (ValueError, TypeError):
            return None

    # ─── Defaults & Enrichment (unchanged from v2) ───────────────────────────

    def _fill_defaults(self, params: Dict[str, Any]) -> None:
        if not params.get("scenario_name"):
            params["scenario_name"] = "Generic Fraud"
            logger.warning("Scenario name missing – defaulting to 'Generic Fraud'")

        if not params.get("rows") or params["rows"] < 1:
            params["rows"] = 10_000
            logger.warning("Row count missing or invalid – defaulting to 10,000")

        if params.get("fraud_ratio") is None:
            params["fraud_ratio"] = 0.05
            logger.warning("Fraud ratio missing – defaulting to 5%%")

        params["fraud_ratio"] = max(0.001, min(0.99, params["fraud_ratio"]))

        fmt_raw = (params.get("output_format") or "csv").lower().strip()
        params["output_format"] = _FORMAT_MAP.get(fmt_raw, "csv")

    def _enrich_scenario(self, params: Dict[str, Any]) -> None:
        """
        Match scenario name against KNOWN_SCENARIOS (substring, case-insensitive).
        Longer keys tested first so 'synthetic identity' beats 'identity fraud'.
        """
        name_lower = params["scenario_name"].lower()

        for key in sorted(KNOWN_SCENARIOS, key=len, reverse=True):
            if key in name_lower:
                meta = KNOWN_SCENARIOS[key]
                params.setdefault("fraud_type", meta["fraud_type"])
                params.setdefault("description", meta["description"])
                params["scenario_name"] = key.title()
                logger.debug("Matched known scenario key: '%s'", key)
                return

        params.setdefault("fraud_type", _DEFAULT_SCENARIO["fraud_type"])
        params.setdefault("description", _DEFAULT_SCENARIO["description"])
        logger.debug("No known scenario matched '%s'", params["scenario_name"])