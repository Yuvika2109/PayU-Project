"""
utils/json_parser.py
Robust JSON extraction from LLM responses that may contain markdown fences,
preamble text, or partial JSON.
"""

import json
import re
from typing import Any, Optional

from utils.logger import get_logger

logger = get_logger("utils.json_parser")


def extract_json(text: str) -> Optional[Any]:
    """
    Attempt multiple strategies to extract a valid JSON object or array
    from raw LLM output.

    Strategies (in order):
        1. Direct parse – the whole string is valid JSON.
        2. Markdown code fence  ```json ... ``` or ``` ... ```.
        3. First { ... } block (greedy balanced extraction).
        4. First [ ... ] block (same).

    Returns the parsed Python object, or None if all strategies fail.
    """
    text = text.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Markdown fence
    fence_match = re.search(
        r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text, re.IGNORECASE
    )
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Balanced brace extraction  { ... }
    extracted = _extract_balanced(text, "{", "}")
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

    # 4. Balanced bracket extraction  [ ... ]
    extracted = _extract_balanced(text, "[", "]")
    if extracted:
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

    logger.warning("JSON extraction failed for text snippet: %.120s …", text)
    return None


def _extract_balanced(text: str, open_ch: str, close_ch: str) -> Optional[str]:
    """Return the first balanced substring starting with *open_ch*."""
    start = text.find(open_ch)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for idx in range(start, len(text)):
        ch = text[idx]

        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue

        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    return None


def safe_dumps(obj: Any, **kwargs) -> str:
    """Serialise *obj* to JSON, falling back to str() on non-serialisable types."""
    def default(o):
        return str(o)

    return json.dumps(obj, default=default, ensure_ascii=False, **kwargs)
