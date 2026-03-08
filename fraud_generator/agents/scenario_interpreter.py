"""
agents/scenario_interpreter.py
Converts free-text user input into a structured scenario parameter dict.

Supports two formats:

  Labelled (multi-line):
    Fraud Scenario: Money Laundering
    Rows: 5000
    Fraud Ratio: 33%
    Output Format: CSV

  Inline (comma-separated):
    Money Laundering, 5000, 33%, csv
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
    "csv": "csv",
    "json": "json",
    "parquet": "parquet",
    "excel": "excel",
    "xlsx": "excel",
    "xls": "excel",
}

_NUMERIC_LIKE = re.compile(r"^[\d,_%.\s]+$")


class ScenarioInterpreterAgent:
    """
    Parse raw user input into a normalised scenario parameter dict.

    Output schema::

        {
            "scenario_name": str,
            "fraud_type":    str,
            "description":   str,
            "rows":          int,
            "fraud_ratio":   float,   # 0.0 - 1.0
            "output_format": str,     # "csv" | "json" | "parquet" | "excel"
        }
    """

    def interpret(self, raw_input: str) -> Dict[str, Any]:
        """Main entry point. Accepts multi-line labelled or comma-separated input."""
        logger.info("Interpreting scenario input (%d chars)", len(raw_input))
        text = raw_input.strip()

        if self._looks_labelled(text):
            params = self._parse_labelled(text)
        else:
            params = self._parse_positional(text)

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

    # ─── Format Detection ─────────────────────────────────────────────────────

    @staticmethod
    def _looks_labelled(text: str) -> bool:
        label_pattern = re.compile(
            r"(?:fraud[\s_-]?scenario|scenario|name|rows?|total[\s_-]?rows?"
            r"|count|size|fraud[\s_-]?ratio|ratio|rate|output[\s_-]?format|format)\s*[:\-=]",
            re.IGNORECASE,
        )
        return bool(label_pattern.search(text))

    # ─── Labelled Parser ──────────────────────────────────────────────────────

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

    # ─── Positional Parser ────────────────────────────────────────────────────

    def _parse_positional(self, text: str) -> Dict[str, Any]:
        """Parse: 'Money Laundering, 5000, 33%, csv'"""
        raw_parts = re.split(r"[,\n]+", text)
        parts = [p.strip() for p in raw_parts if p.strip()]

        params: Dict[str, Any] = {}

        # Pass 1: collect scenario name tokens (leading non-numeric parts)
        name_tokens: list = []
        remaining_start = 0

        for i, part in enumerate(parts):
            looks_int = bool(re.match(r"^[\d,_]+$", part))
            looks_ratio = bool(re.search(r"\d.*%", part))
            looks_float = bool(re.match(r"^0?\.\d+$", part))
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

    # ─── Field Helpers ────────────────────────────────────────────────────────

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

    # ─── Defaults & Enrichment ────────────────────────────────────────────────

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