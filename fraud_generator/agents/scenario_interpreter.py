"""
agents/scenario_interpreter.py  (v5)
Converts free-text user input into a structured scenario parameter dict.

v5 fixes:
  1. NLPScenarioExtractor prompt now includes disambiguation examples so
     the LLM doesn't conflate "account takeover" with "card testing".
     Instructs LLM to extract a descriptive name, not over-normalise.

  2. _enrich_scenario now matches keywords against the FULL raw user input
     in addition to the extracted scenario_name, so "breaks into someone's
     online banking account and makes large purchases" correctly maps to
     Account Takeover even if the LLM returned "Card Fraud" as the name.

  3. params["user_context"] stores the original raw sentence and is passed
     to the blueprint generator. This means the blueprint LLM sees the
     user's own words ("amounts over per-diem", "luxury hotels", "small
     micro-charges") as direct signal — not just a sanitised summary.
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
            "Attacker systematically tests BIN ranges with micro-transactions "
            "($0.01-$2.00) to identify valid card numbers. Transactions occur "
            "in rapid bursts of 15-80 charges within 10 minutes, off-hours (1-4am), "
            "from foreign IPs, against a single merchant."
        ),
    },
    "card testing": {
        "fraud_type": "Card-Not-Present Fraud",
        "description": (
            "Small test transactions ($0.01-$5.00) verify stolen card credentials "
            "before using them for larger purchases. Burst pattern, foreign IP, "
            "same device, off-hours timing."
        ),
    },
    "account takeover": {
        "fraud_type": "Identity Fraud",
        "description": (
            "Fraudster gains access to a legitimate account and immediately makes "
            "high-value purchases ($200-$5000) at electronics, luxury, or travel "
            "merchants before the victim notices. Chain of 3-8 escalating transactions "
            "from a new device and foreign IP."
        ),
    },
    "money laundering": {
        "fraud_type": "Financial Crime",
        "description": (
            "Illicit funds passed through multiple transactions structured to stay "
            "under the $10,000 reporting threshold ($1,000-$9,999 each). "
            "Network/smurfing pattern across many accounts and merchants."
        ),
    },
    "refund fraud": {
        "fraud_type": "Return / Refund Abuse",
        "description": (
            "Fraudster exploits refund policies — normal-looking retail purchase "
            "amounts ($30-$400) that are later disputed. Independent transactions "
            "that appear legitimate."
        ),
    },
    "identity fraud": {
        "fraud_type": "Identity Theft",
        "description": (
            "Stolen personal information used to open accounts or make purchases "
            "($100-$3000). Escalating credit use over days/weeks, new device, "
            "address mismatch."
        ),
    },
    "phishing": {
        "fraud_type": "Social Engineering",
        "description": (
            "Deceptive communications trick victims into authorising transfers. "
            "Normal-looking amounts ($50-$2000) from victim's own device but "
            "unusual recipient accounts or merchants."
        ),
    },
    "synthetic identity": {
        "fraud_type": "Identity Fraud",
        "description": (
            "Fabricated PII used to open new accounts. Slow build-up of small "
            "transactions ($10-$500) to establish credit history, followed by "
            "a large bust-out ($1000-$5000) before abandoning the identity."
        ),
    },
    "friendly fraud": {
        "fraud_type": "Chargeback Fraud",
        "description": (
            "Legitimate cardholder disputes valid transactions ($50-$500) to "
            "obtain refunds while keeping goods. Amounts match real consumer "
            "purchases — indistinguishable from normal transactions."
        ),
    },
    "triangulation fraud": {
        "fraud_type": "E-commerce Fraud",
        "description": (
            "Fraudster collects payment via fake storefront then fulfils orders "
            "using stolen cards ($50-$1500). Burst of card-not-present transactions "
            "across multiple e-commerce merchants."
        ),
    },
    "upi fraud": {
        "fraud_type": "Real-Time Payment Fraud",
        "description": (
            "Fraudster abuses UPI real-time transfers using stolen credentials, "
            "social engineering, or mule VPAs. Mix of collect-request and push "
            "patterns with rapid transaction velocity ($20-$2000), unusual payees, "
            "and activity concentrated in off-hours."
        ),
    },
    "upi collect scam": {
        "fraud_type": "Authorised Push Payment Fraud",
        "description": (
            "Victim is tricked into approving fake UPI collect requests that appear "
            "legitimate. Repeated requests in short windows ($50-$1500), high failure "
            "noise before successful debits, and abrupt payee changes."
        ),
    },
    "upi mule transfers": {
        "fraud_type": "Money Mule Network Fraud",
        "description": (
            "Compromised or coerced UPI accounts funnel funds to mule VPAs in chained "
            "hops. Frequent medium-value transfers ($200-$5000), many recipient accounts, "
            "and network-like movement designed to evade traceability."
        ),
    },
}

# Semantic aliases: user phrases that map to a known scenario key
# Used to match raw text when extracted scenario_name doesn't keyword-match
_SEMANTIC_ALIASES: Dict[str, str] = {
    # Account takeover signals
    "breaks into":          "account takeover",
    "hacks into":           "account takeover",
    "gains access to":      "account takeover",
    "compromised account":  "account takeover",
    "stolen credentials":   "account takeover",
    "hijacks":              "account takeover",
    "takes over":           "account takeover",
    "large purchases":      "account takeover",
    "drains the account":   "account takeover",
    # BIN attack signals
    "bin range":            "bin attack",
    "test.*bin":            "bin attack",
    "probe.*card":          "bin attack",
    "micro.transact":       "bin attack",
    "tiny.*transact":       "bin attack",
    "small.*transact.*card":"bin attack",
    "test.*card.*work":     "bin attack",
    "test a bunch of card": "bin attack",
    "find.*valid.*card":    "bin attack",
    # Card testing signals
    "verify.*card":         "card testing",
    "valid.*card.*detail":  "card testing",
    "stolen card.*detail":  "card testing",
    "small.*charge.*valid": "card testing",
    "which.*ones.*valid":   "card testing",
    "see.*which.*valid":    "card testing",
    "check.*card.*valid":   "card testing",
    # Money laundering signals
    "structur":             "money laundering",
    "smurfing":             "money laundering",
    "wash.*money":          "money laundering",
    "launder":              "money laundering",
    "under.*report":        "money laundering",
    "10.000.*threshold":    "money laundering",
    # Phishing signals
    "trick.*victim":        "phishing",
    "deceiv":               "phishing",
    "fake.*email":          "phishing",
    "social engineer":      "phishing",
    # Synthetic identity
    "fake.*identit":        "synthetic identity",
    "fabricat.*pii":        "synthetic identity",
    "bust.out":             "synthetic identity",
    # UPI fraud signals
    "upi":                  "upi fraud",
    "collect request":      "upi collect scam",
    "payment request":      "upi collect scam",
    "approve.*collect":     "upi collect scam",
    "vpa":                  "upi fraud",
    "mule.*upi":            "upi mule transfers",
    "mule account":         "upi mule transfers",
    "peer.to.peer transfer":"upi fraud",
    "p2p transfer":         "upi fraud",
    "qr.*upi":              "upi fraud",
}

_DEFAULT_SCENARIO = {
    "fraud_type": "Generic Fraud",
    "description": "Custom fraud scenario as described by the user.",
}

_FORMAT_MAP: Dict[str, str] = {
    "csv":     "csv",
    "json":    "json",
    "parquet": "parquet",
    "excel":   "excel",
    "xlsx":    "excel",
    "xls":     "excel",
}

_NUMERIC_LIKE = re.compile(r"^[\d,_%.\s]+$")


# ─── NLP Parameter Extractor ──────────────────────────────────────────────────

class NLPScenarioExtractor:
    """
    Uses the LLM to extract rows/ratio/format/scenario_name from a sentence.

    v5: Prompt now instructs the LLM to return the user's OWN descriptive
    name rather than over-normalising to a standard label. This prevents
    "breaks into an account" being returned as "Card Testing" just because
    the LLM associates it with stolen card scenarios. Classification is
    handled downstream by _enrich_scenario + ScenarioEnricher.
    """

    _PROMPT = """\
You are a data extraction assistant. Extract fraud dataset parameters from the user's request.

Return ONLY a valid JSON object with exactly these four keys:
  "scenario_name"  : string — a SHORT descriptive name for this fraud scenario (3-6 words).
                     Use the user's own language where possible.
                     DO NOT over-normalise — if unsure, echo the user's description.
                     Examples of CORRECT extraction:
                       "fraudsters test cards with tiny charges" -> "BIN Attack"
                       "breaks into account, makes large purchases" -> "Account Takeover"
                       "employee uses corporate card at luxury hotels" -> "Corporate Card Abuse"
                       "fake invoices sent to accounts payable" -> "Invoice Fraud"
                       "structuring deposits under $10,000" -> "Money Laundering"
                     Examples of WRONG extraction (do NOT do this):
                       "breaks into account" -> "Card Testing"  [WRONG — no card testing here]
                       "hacks into banking app" -> "Phishing"   [WRONG — that is account takeover]
  "rows"           : integer — total rows/transactions requested, or null if not stated
  "fraud_ratio"    : float   — fraud ratio as decimal 0-1, or null if not stated
                               (convert: "10%" -> 0.10, "one-third" -> 0.33, "8 percent" -> 0.08)
  "output_format"  : string  — one of: csv, json, parquet, excel — or null if not stated

Rules:
- "k" or "thousand" means x1000. "million" or "M" means x1000000.
- Written numbers: "twenty thousand" -> 20000, "half a million" -> 500000.
- If a field is genuinely absent, return null — do NOT guess.
- Return ONLY the JSON object — no markdown, no explanation.

User request:
{user_input}
"""

    def extract(self, raw_input: str) -> Dict[str, Any]:
        try:
            from core.llm_interface import generate_response
            from utils.json_parser import extract_json

            prompt = self._PROMPT.format(user_input=raw_input.strip())
            raw = generate_response(prompt, temperature=0.0, max_tokens=256)
            parsed = extract_json(raw)
            if not isinstance(parsed, dict):
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
                if r > 1.0:
                    r = r / 100.0
                params["fraud_ratio"] = round(r, 4)

            fmt = parsed.get("output_format")
            if isinstance(fmt, str) and fmt.strip():
                params["output_format"] = _FORMAT_MAP.get(
                    fmt.lower().strip(), fmt.lower().strip()
                )

            logger.info("NLP extractor result: %s", params)
            return params

        except Exception as exc:
            logger.warning("NLP extractor failed (%s) — regex fallback.", exc)
            return {}


# ─── Scenario Enricher ────────────────────────────────────────────────────────

class ScenarioEnricher:
    """
    For scenarios that don't match any KNOWN_SCENARIOS keyword or alias,
    calls the LLM to infer a precise fraud_type and behavioural description.
    """

    _PROMPT = """\
You are a fraud analytics expert. A user has described a fraud scenario in their own words.
Your job is to extract a precise fraud classification and a detailed behavioural description.

Return ONLY a valid JSON object with exactly two keys:
  "fraud_type"  : string — the formal fraud category
  "description" : string — a 2-4 sentence behavioural description covering:
                  (a) what the fraudster does and their goal
                  (b) realistic transaction AMOUNT RANGE in dollars (be specific, not "variable")
                  (c) transaction PATTERN — burst/chain/network/independent, timing, frequency
                  (d) key SIGNALS that distinguish fraud from legitimate behaviour
                  (e) typical merchants, channels, or locations involved

IMPORTANT: Extract amount information from the user's OWN description if they gave it.
For example: if the user said "amounts over per-diem policy", incorporate realistic
per-diem figures ($50-$150/day) and mark amounts above that as fraudulent.
If the user said "small micro-charges", use $0.01-$5.00 range.
If the user said "large B2B transfers", use $50,000-$500,000 range.

Rules:
- Be specific about amounts — give dollar ranges, not vague terms.
- The description will be used to generate a synthetic dataset, so include enough
  numeric detail for a data engineer to implement it.
- Return ONLY the JSON object — no markdown, no explanation.

User's scenario description:
{scenario_text}
"""

    def enrich(self, scenario_name: str, raw_user_input: str) -> Dict[str, str]:
        try:
            from core.llm_interface import generate_response
            from utils.json_parser import extract_json

            scenario_text = (
                f"Scenario name: {scenario_name}\n"
                f"User's full description: {raw_user_input.strip()}"
            )
            prompt = self._PROMPT.format(scenario_text=scenario_text)
            logger.info("ScenarioEnricher: calling LLM for '%s'", scenario_name)

            raw = generate_response(prompt, temperature=0.1, max_tokens=400)
            parsed = extract_json(raw)

            if not isinstance(parsed, dict):
                return dict(_DEFAULT_SCENARIO)

            fraud_type  = parsed.get("fraud_type", "").strip()
            description = parsed.get("description", "").strip()

            if not fraud_type or not description:
                return dict(_DEFAULT_SCENARIO)

            logger.info("ScenarioEnricher: type='%s'", fraud_type)
            return {"fraud_type": fraud_type, "description": description}

        except Exception as exc:
            logger.warning("ScenarioEnricher failed (%s) — fallback.", exc)
            return dict(_DEFAULT_SCENARIO)


# ─── Main Interpreter Agent ───────────────────────────────────────────────────

class ScenarioInterpreterAgent:
    """
    Parse raw user input into a normalised scenario parameter dict.

    Output schema::

        {
            "scenario_name": str,
            "fraud_type":    str,
            "description":   str,
            "rows":          int,
            "fraud_ratio":   float,
            "output_format": str,
            "user_context":  str,   ← raw user sentence (new in v5)
        }
    """

    def __init__(self):
        self._nlp      = NLPScenarioExtractor()
        self._enricher = ScenarioEnricher()
        self._raw_input: str = ""

    def interpret(self, raw_input: str,
                  fraud_category: str = "card") -> Dict[str, Any]:
        """
        Parse raw user input into normalised scenario params.

        Parameters
        ----------
        raw_input       : Free-text / labelled / positional scenario description.
        fraud_category  : "card" | "upi" | "other" — selected by user in the UI.
                          Injected into params so blueprint_generator can propagate
                          it to the blueprint and DatasetEngine can route correctly.
        """
        logger.info("Interpreting scenario input (%d chars)", len(raw_input))
        self._raw_input = raw_input.strip()
        text = raw_input.strip()

        if self._looks_labelled(text):
            logger.info("Input mode: LABELLED")
            params = self._parse_labelled(text)
        elif self._looks_positional(text):
            logger.info("Input mode: POSITIONAL")
            params = self._parse_positional(text)
        else:
            logger.info("Input mode: NATURAL LANGUAGE")
            params = self._nlp.extract(text)

            fallback = self._regex_number_fallback(text)
            for k, v in fallback.items():
                params.setdefault(k, v)

            if not params.get("scenario_name"):
                params["scenario_name"] = self._scenario_from_sentence(text) or ""

        # Always store the raw input for blueprint context (v5)
        params["user_context"]    = self._raw_input
        # Store fraud category so DatasetEngine can route to the right generator
        params["fraud_category"]  = fraud_category.lower().strip() or "card"

        self._fill_defaults(params)
        self._enrich_scenario(params)

        logger.info(
            "Interpreted: name='%s'  rows=%d  ratio=%.2f%%  format=%s",
            params["scenario_name"],
            params["rows"],
            params["fraud_ratio"] * 100,
            params["output_format"],
        )
        return params

    # ─── Input-Mode Detection ─────────────────────────────────────────────────

    @staticmethod
    def _looks_labelled(text: str) -> bool:
        label_pattern = re.compile(
            r"(?:fraud[\s_-]?scenario|scenario|name|rows?|total[\s_-]?rows?"
            r"|count|size|fraud[\s_-]?ratio|ratio|rate|output[\s_-]?format|format)\s*[:\-=]",
            re.IGNORECASE,
        )
        return bool(label_pattern.search(text))

    @staticmethod
    def _looks_positional(text: str) -> bool:
        if "\n" in text:
            return False
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if len(parts) < 2:
            return False
        return all(len(p.split()) <= 3 for p in parts)

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
        raw_parts = re.split(r"[,\n]+", text)
        parts = [p.strip() for p in raw_parts if p.strip()]

        params: Dict[str, Any] = {}
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

    # ─── NL Helpers ───────────────────────────────────────────────────────────

    def _regex_number_fallback(self, text: str) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        row_patterns = [
            (r"(\d[\d,]*)\s*k\b",                                              1_000),
            (r"(\d[\d,]*)\s*(?:thousand)\b",                                   1_000),
            (r"(\d[\d,]*)\s*(?:million|M)\b",                              1_000_000),
            (r"(\d[\d,]*)\s*(?:rows?|transactions?|records?|samples?|entries)",    1),
        ]
        for pat, multiplier in row_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m and "rows" not in params:
                try:
                    params["rows"] = int(m.group(1).replace(",", "")) * multiplier
                except ValueError:
                    pass
                break

        for pat in [r"(\d+(?:\.\d+)?)\s*(?:%|percent(?:age)?)", r"\b(0\.\d+)\b"]:
            m = re.search(pat, text, re.IGNORECASE)
            if m and "fraud_ratio" not in params:
                r = self._parse_ratio(m.group(0))
                if r is not None:
                    params["fraud_ratio"] = r
                break

        for fmt_key in _FORMAT_MAP:
            if re.search(r"\b" + fmt_key + r"\b", text, re.IGNORECASE):
                params.setdefault("output_format", _FORMAT_MAP[fmt_key])
                break

        return {k: v for k, v in params.items() if v is not None}

    def _scenario_from_sentence(self, text: str) -> Optional[str]:
        """Keyword scan on raw text — longest match first."""
        lower = text.lower()
        for key in sorted(KNOWN_SCENARIOS, key=len, reverse=True):
            if key in lower:
                return key.title()
        return None

    def _semantic_match(self, text: str) -> Optional[str]:
        """
        Scan raw text for semantic aliases that indicate a known scenario
        even when the exact keyword isn't present.
        e.g. 'breaks into account' -> 'account takeover'
        Returns the matched KNOWN_SCENARIOS key or None.
        """
        lower = text.lower()
        # Count alias matches per scenario to find best fit
        scenario_scores: Dict[str, int] = {}
        for phrase, scenario_key in _SEMANTIC_ALIASES.items():
            if re.search(phrase, lower):
                scenario_scores[scenario_key] = scenario_scores.get(scenario_key, 0) + 1

        if not scenario_scores:
            return None
        # Return highest-scoring scenario
        best = max(scenario_scores, key=lambda k: scenario_scores[k])
        logger.info(
            "Semantic match: '%s' (score=%d, all=%s)",
            best, scenario_scores[best], scenario_scores,
        )
        return best

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
            params["scenario_name"] = "Custom Fraud"
            logger.warning("Scenario name missing – defaulting to 'Custom Fraud'")

        if not params.get("rows") or params["rows"] < 1:
            params["rows"] = 10_000
            logger.warning("Row count missing – defaulting to 10,000")

        if params.get("fraud_ratio") is None:
            params["fraud_ratio"] = 0.33
            logger.warning("Fraud ratio missing – defaulting to 33%")

        params["fraud_ratio"] = max(0.001, min(0.99, params["fraud_ratio"]))

        fmt_raw = (params.get("output_format") or "csv").lower().strip()
        params["output_format"] = _FORMAT_MAP.get(fmt_raw, "csv")

    def _enrich_scenario(self, params: Dict[str, Any]) -> None:
        """
        Attach fraud_type and description.

        Priority order (v5):
          1. Keyword match on raw user input (most reliable)
          2. Keyword match on extracted scenario_name
          3. Semantic alias match on raw user input
          4. ScenarioEnricher LLM call for genuinely unknown scenarios
        """
        raw_lower  = self._raw_input.lower()
        name_lower = params["scenario_name"].lower()

        # ── 1. Keyword match on raw user input ────────────────────────────────
        for key in sorted(KNOWN_SCENARIOS, key=len, reverse=True):
            if key in raw_lower:
                meta = KNOWN_SCENARIOS[key]
                params.setdefault("fraud_type",  meta["fraud_type"])
                params.setdefault("description", meta["description"])
                params["scenario_name"] = key.title()
                logger.info("Matched known scenario on raw input: '%s'", key)
                return

        # ── 2. Keyword match on extracted scenario_name ───────────────────────
        for key in sorted(KNOWN_SCENARIOS, key=len, reverse=True):
            if key in name_lower:
                meta = KNOWN_SCENARIOS[key]
                params.setdefault("fraud_type",  meta["fraud_type"])
                params.setdefault("description", meta["description"])
                params["scenario_name"] = key.title()
                logger.info("Matched known scenario on name: '%s'", key)
                return

        # ── 3. Semantic alias match on raw input ──────────────────────────────
        matched_key = self._semantic_match(self._raw_input)
        if matched_key and matched_key in KNOWN_SCENARIOS:
            meta = KNOWN_SCENARIOS[matched_key]
            params.setdefault("fraud_type",  meta["fraud_type"])
            params.setdefault("description", meta["description"])
            params["scenario_name"] = matched_key.title()
            logger.info("Semantic alias match: '%s'", matched_key)
            return

        # ── 4. Unknown scenario — ScenarioEnricher LLM call ──────────────────
        logger.info("Unknown scenario '%s' — invoking ScenarioEnricher", params["scenario_name"])
        enriched = self._enricher.enrich(
            scenario_name=params["scenario_name"],
            raw_user_input=self._raw_input or params["scenario_name"],
        )
        params.setdefault("fraud_type",  enriched["fraud_type"])
        params.setdefault("description", enriched["description"])
        logger.info("ScenarioEnricher: type='%s'", params["fraud_type"])