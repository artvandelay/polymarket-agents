"""
Shared utilities for Polymarket data handling.
"""

from __future__ import annotations

import json
from typing import Any


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
