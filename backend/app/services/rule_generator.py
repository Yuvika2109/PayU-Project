# """
# Rule Generation Service
# ────────────────────────
# Takes a fraud scenario (text or name) + schema context and calls
# the LLM to produce a structured list of FraudRule objects.

# Supports two modes:
#   NORMAL   – only the user prompt is used
#   ASSISTED – blueprint JSON is passed alongside the prompt (future)
# """
# from __future__ import annotations

# import logging
# import uuid
# from typing import Optional

# from app.core.llm_client import get_llm_client
# from app.core.schema_detector import get_schema_context
# from app.models.schemas import (
#     FraudRule,
#     GenerateRulesRequest,
#     GenerateRulesResponse,
#     OperatorType,
#     RuleCategory,
#     RuleCondition,
#     RuleMode,
#     RuleSeverity,
#     SchemaType,
# )

# logger = logging.getLogger(__name__)

# # ─── System prompt ────────────────────────────────────────────────────────────

# _SYSTEM_PROMPT = """\
# You are a senior fraud analytics engineer specialising in payment fraud detection.
# Your task is to generate precise, actionable fraud detection rules for a given fraud scenario.

# You must return a single JSON object — no markdown, no explanation, just JSON — with this exact structure:

# {
#   "scenario_summary": "<1-2 sentence description of the fraud pattern>",
#   "rules": [
#     {
#       "id": "R001",
#       "name": "<short rule name>",
#       "description": "<what this rule detects and why it is a fraud signal>",
#       "category": "<one of: velocity, amount, device, geography, authentication, behavioral, account, merchant>",
#       "severity": "<high | medium | low>",
#       "logic_expression": "<human-readable expression, e.g. 'transaction_amount < 5 AND velocity_24h > 10'>",
#       "match_any": false,
#       "tags": ["<tag1>", "<tag2>"],
#       "conditions": [
#         {
#           "field": "<exact column name from the dataset>",
#           "operator": "<gt | gte | lt | lte | eq | neq | in | not_in | contains>",
#           "value": <number, string, or list>,
#           "description": "<why this condition is a fraud signal>"
#         }
#       ]
#     }
#   ]
# }

# Rules for good rule design:
# - Each rule must map to ACTUAL columns available in the dataset.
# - Prefer specific numeric thresholds over vague descriptions.
# - High severity = strong fraud signal (precision > 70%). Medium = suspicious anomaly. Low = weak signal needing combination.
# - Conditions should be AND-combined by default (match_any: false); use match_any: true only when alternatives make equal sense.
# - Cover multiple detection dimensions: velocity, amount anomaly, geography, device, time-of-day, account behaviour.
# - Do NOT invent columns that are not in the dataset.
# """

# # ─── Prompt builders ─────────────────────────────────────────────────────────

# def _build_normal_prompt(req: GenerateRulesRequest, schema_type: SchemaType) -> str:
#     schema_ctx = get_schema_context(schema_type, req.available_columns)
#     return (
#         f"Fraud scenario: \"{req.scenario}\"\n\n"
#         f"Dataset context: {schema_ctx}\n\n"
#         f"Generate {req.num_rules} fraud detection rules for this scenario. "
#         "Return only the JSON object described in your instructions."
#     )


# def _build_assisted_prompt(req: GenerateRulesRequest, schema_type: SchemaType) -> str:
#     schema_ctx = get_schema_context(schema_type, req.available_columns)
#     blueprint_str = str(req.blueprint)[:2000]  # guard token budget
#     return (
#         f"Fraud scenario: \"{req.scenario}\"\n\n"
#         f"Dataset context: {schema_ctx}\n\n"
#         f"Fraud blueprint (pattern detail):\n{blueprint_str}\n\n"
#         f"Generate {req.num_rules} fraud detection rules aligned with the blueprint. "
#         "Prioritise the features and thresholds mentioned in the blueprint. "
#         "Return only the JSON object described in your instructions."
#     )


# # ─── Parsing helpers ──────────────────────────────────────────────────────────

# def _parse_operator(raw: str) -> OperatorType:
#     mapping = {
#         "gt": OperatorType.GT, ">": OperatorType.GT,
#         "gte": OperatorType.GTE, ">=": OperatorType.GTE,
#         "lt": OperatorType.LT, "<": OperatorType.LT,
#         "lte": OperatorType.LTE, "<=": OperatorType.LTE,
#         "eq": OperatorType.EQ, "==": OperatorType.EQ, "=": OperatorType.EQ,
#         "neq": OperatorType.NEQ, "!=": OperatorType.NEQ,
#         "in": OperatorType.IN,
#         "not_in": OperatorType.NOT_IN,
#         "contains": OperatorType.CONTAINS,
#     }
#     return mapping.get(str(raw).lower().strip(), OperatorType.EQ)


# def _parse_category(raw: str) -> RuleCategory:
#     try:
#         return RuleCategory(raw.lower())
#     except ValueError:
#         return RuleCategory.BEHAVIORAL


# def _parse_severity(raw: str) -> RuleSeverity:
#     try:
#         return RuleSeverity(raw.lower())
#     except ValueError:
#         return RuleSeverity.MEDIUM


# def _parse_rules(raw_rules: list[dict]) -> list[FraudRule]:
#     rules = []
#     for i, r in enumerate(raw_rules):
#         rule_id = r.get("id") or f"R{i+1:03d}"

#         raw_conditions = r.get("conditions", [])
#         conditions = []
#         for c in raw_conditions:
#             try:
#                 conditions.append(RuleCondition(
#                     field=c.get("field", ""),
#                     operator=_parse_operator(c.get("operator", "eq")),
#                     value=c.get("value"),
#                     description=c.get("description", ""),
#                 ))
#             except Exception as exc:
#                 logger.warning("Skipping malformed condition in rule %s: %s", rule_id, exc)

#         try:
#             rule = FraudRule(
#                 id=rule_id,
#                 name=r.get("name", f"Rule {rule_id}"),
#                 description=r.get("description", ""),
#                 category=_parse_category(r.get("category", "behavioral")),
#                 severity=_parse_severity(r.get("severity", "medium")),
#                 logic_expression=r.get("logic_expression", ""),
#                 conditions=conditions,
#                 match_any=bool(r.get("match_any", False)),
#                 tags=r.get("tags", []),
#             )
#             rules.append(rule)
#         except Exception as exc:
#             logger.warning("Skipping malformed rule %s: %s", rule_id, exc)

#     return rules


# # ─── Main service function ────────────────────────────────────────────────────

# async def generate_rules(
#     req: GenerateRulesRequest,
#     schema_type: Optional[SchemaType] = None,
# ) -> GenerateRulesResponse:
#     """
#     Call the LLM to generate fraud detection rules for the given scenario.
#     """
#     effective_schema = schema_type or req.schema_type or SchemaType.EMVCO

#     llm = get_llm_client()

#     if req.mode == RuleMode.ASSISTED and req.blueprint:
#         user_prompt = _build_assisted_prompt(req, effective_schema)
#     else:
#         user_prompt = _build_normal_prompt(req, effective_schema)

#     logger.info(
#         "Generating rules | scenario=%r | schema=%s | model=%s | num=%d",
#         req.scenario[:60], effective_schema, llm.model, req.num_rules,
#     )

#     response_json = await llm.chat_json(
#         system=_SYSTEM_PROMPT,
#         user=user_prompt,
#         temperature=0.2,
#     )

#     scenario_summary = response_json.get("scenario_summary", req.scenario)
#     raw_rules        = response_json.get("rules", [])

#     if not raw_rules:
#         raise ValueError(
#             "LLM returned no rules. Check the model is running and the prompt is valid."
#         )

#     rules = _parse_rules(raw_rules)
#     logger.info("Generated %d rules for scenario %r", len(rules), req.scenario[:60])

#     return GenerateRulesResponse(
#         scenario_summary=scenario_summary,
#         schema_type=effective_schema,
#         rules=rules,
#         model_used=llm.model,
#     )


"""
Rule Generation Service
────────────────────────
Takes a fraud scenario (text or name) + schema context and calls
the LLM to produce a structured list of FraudRule objects.

Supports two modes:
  NORMAL   – only the user prompt is used
  ASSISTED – blueprint JSON is passed alongside the prompt (future)
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

from app.core.llm_client import get_llm_client
from app.core.schema_detector import get_schema_context
from app.models.schemas import (
    FraudRule,
    GenerateRulesRequest,
    GenerateRulesResponse,
    OperatorType,
    RuleCategory,
    RuleCondition,
    RuleMode,
    RuleSeverity,
    SchemaType,
)

logger = logging.getLogger(__name__)

# ─── System prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior fraud analytics engineer specialising in payment fraud detection.
Your task is to generate precise, actionable fraud detection rules for a given fraud scenario.

You must return a single JSON object — no markdown, no explanation, just JSON — with this exact structure:

{
  "scenario_summary": "<1-2 sentence description of the fraud pattern>",
  "rules": [
    {
      "id": "R001",
      "name": "<short rule name>",
      "description": "<what this rule detects and why it is a fraud signal>",
      "category": "<one of: velocity, amount, device, geography, authentication, behavioral, account, merchant>",
      "severity": "<high | medium | low>",
      "logic_expression": "<human-readable expression, e.g. 'transaction_amount < 5 AND velocity_24h > 10'>",
      "match_any": false,
      "tags": ["<tag1>", "<tag2>"],
      "conditions": [
        {
          "field": "<exact column name from the dataset>",
          "operator": "<gt | gte | lt | lte | eq | neq | in | not_in | contains>",
          "value": "<numeric threshold, string or JSON array>",
          "description": "<why this condition is a fraud signal>"
        }
      ]
    }
  ]
}

Rules for good rule design:
- Each rule must map to ACTUAL columns available in the dataset.
- Prefer specific numeric thresholds over vague descriptions.
- High severity = strong fraud signal (precision > 70%). Medium = suspicious anomaly. Low = weak signal needing combination.
- Conditions should be AND-combined by default (match_any: false); use match_any: true only when alternatives make equal sense.
- Cover multiple detection dimensions: velocity, amount anomaly, geography, device, time-of-day, account behaviour.
- Do NOT invent columns that are not in the dataset.
"""

# ─── Prompt builders ─────────────────────────────────────────────────────────

_MAX_RULES_PER_CALL = 5  # safety cap for small models


def _effective_num_rules(req: GenerateRulesRequest) -> int:
    try:
        n = int(req.num_rules)
    except Exception:
        n = 5
    return max(1, min(n, _MAX_RULES_PER_CALL))


def _build_normal_prompt(req: GenerateRulesRequest, schema_type: SchemaType) -> str:
    schema_ctx = get_schema_context(schema_type, req.available_columns)
    n = _effective_num_rules(req)
    return (
        f'Fraud scenario: "{req.scenario}"\n\n'
        f"Dataset context: {schema_ctx}\n\n"
        f"Generate {n} fraud detection rules for this scenario. "
        "Return only the JSON object described in your instructions."
    )


def _build_assisted_prompt(req: GenerateRulesRequest, schema_type: SchemaType) -> str:
    schema_ctx = get_schema_context(schema_type, req.available_columns)
    blueprint_str = str(getattr(req, "blueprint", ""))[:2000]  # guard token budget
    n = _effective_num_rules(req)
    return (
        f'Fraud scenario: "{req.scenario}"\n\n'
        f"Dataset context: {schema_ctx}\n\n"
        f"Fraud blueprint (pattern detail):\n{blueprint_str}\n\n"
        f"Generate {n} fraud detection rules aligned with the blueprint. "
        "Prioritise the features and thresholds mentioned in the blueprint. "
        "Return only the JSON object described in your instructions."
    )

# ─── Parsing helpers ─────────────────────────────────────────────────────────-


def _parse_operator(raw: str) -> OperatorType:
    mapping = {
        "gt": OperatorType.GT,
        ">": OperatorType.GT,
        "gte": OperatorType.GTE,
        ">=": OperatorType.GTE,
        "lt": OperatorType.LT,
        "<": OperatorType.LT,
        "lte": OperatorType.LTE,
        "<=": OperatorType.LTE,
        "eq": OperatorType.EQ,
        "==": OperatorType.EQ,
        "=": OperatorType.EQ,
        "neq": OperatorType.NEQ,
        "!=": OperatorType.NEQ,
        "in": OperatorType.IN,
        "not_in": OperatorType.NOT_IN,
        "contains": OperatorType.CONTAINS,
    }
    return mapping.get(str(raw).lower().strip(), OperatorType.EQ)


def _parse_category(raw: str) -> RuleCategory:
    try:
        return RuleCategory(raw.lower())
    except ValueError:
        return RuleCategory.BEHAVIORAL


def _parse_severity(raw: str) -> RuleSeverity:
    try:
        return RuleSeverity(raw.lower())
    except ValueError:
        return RuleSeverity.MEDIUM


def _parse_rules(raw_rules: List[Dict[str, Any]]) -> List[FraudRule]:
    rules: List[FraudRule] = []
    for i, r in enumerate(raw_rules):
        rule_id = r.get("id") or f"R{i+1:03d}"

        raw_conditions = r.get("conditions", []) or []
        conditions: List[RuleCondition] = []
        for c in raw_conditions:
            try:
                conditions.append(
                    RuleCondition(
                        field=c.get("field", "") or "",
                        operator=_parse_operator(c.get("operator", "eq")),
                        value=c.get("value"),
                        description=c.get("description", "") or "",
                    )
                )
            except Exception as exc:
                logger.warning("Skipping malformed condition in rule %s: %s", rule_id, exc)

        try:
            rule = FraudRule(
                id=rule_id,
                name=r.get("name", f"Rule {rule_id}") or f"Rule {rule_id}",
                description=r.get("description", "") or "",
                category=_parse_category(r.get("category", "behavioral")),
                severity=_parse_severity(r.get("severity", "medium")),
                logic_expression=r.get("logic_expression", "") or "",
                conditions=conditions,
                match_any=bool(r.get("match_any", False)),
                tags=r.get("tags", []) or [],
            )
            rules.append(rule)
        except Exception as exc:
            logger.warning("Skipping malformed rule %s: %s", rule_id, exc)

    return rules

# ─── Main service function ────────────────────────────────────────────────────


async def generate_rules(
    req: GenerateRulesRequest,
    schema_type: Optional[SchemaType] = None,
) -> GenerateRulesResponse:
    """
    Call the LLM to generate fraud detection rules for the given scenario.
    """
    effective_schema = schema_type or req.schema_type or SchemaType.EMVCO
    llm = get_llm_client()

    if req.mode == RuleMode.ASSISTED and getattr(req, "blueprint", None):
        user_prompt = _build_assisted_prompt(req, effective_schema)
    else:
        user_prompt = _build_normal_prompt(req, effective_schema)

    logger.info(
        "Generating rules | scenario=%r | schema=%s | model=%s | requested_num=%d",
        req.scenario[:60],
        effective_schema,
        llm.model,
        req.num_rules,
    )

    response_json = await llm.chat_json(
        system=_SYSTEM_PROMPT,
        user=user_prompt,
        temperature=0.2,
    )

    if not isinstance(response_json, dict):
        raise ValueError(f"LLM did not return a JSON object: {type(response_json)}")

    scenario_summary = response_json.get("scenario_summary", req.scenario)
    raw_rules = response_json.get("rules", [])

    if not raw_rules:
        raise ValueError(
            "LLM returned no rules. Check the model is running and the prompt is valid."
        )

    rules = _parse_rules(raw_rules)
    logger.info("Generated %d rules for scenario %r", len(rules), req.scenario[:60])

    return GenerateRulesResponse(
        scenario_summary=scenario_summary,
        schema_type=effective_schema,
        rules=rules,
        model_used=llm.model,
    )