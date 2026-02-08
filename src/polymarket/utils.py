"""Shared utilities."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

API_TIMEOUT = 30.0

def safe_json(val: Any) -> list:
    """Parse a JSON-encoded string, or return as-is if already a list."""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return []
    return []
