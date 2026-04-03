"""Helpers for writing strict JSON result files."""

from __future__ import annotations

import json
import math
from typing import Any


def sanitize_for_json(value: Any) -> Any:
    """Convert non-finite floats into strict-JSON-safe string values."""

    if isinstance(value, dict):
        return {str(key): sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


def dumps_strict_json(value: Any, *, indent: int | None = None) -> str:
    """Serialize data as strict JSON without NaN/Infinity tokens."""

    return json.dumps(sanitize_for_json(value), indent=indent, allow_nan=False)
