"""Utilities for keeping generated artifacts compatible with strict JSON stores."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


def normalize_json_value(value: Any) -> Any:
    """Return a JSON-safe copy while preserving non-finite numeric meaning.

    Python's JSON codec accepts and emits ``NaN`` and ``Infinity`` by default,
    but PostgreSQL JSONB (correctly) rejects those non-standard tokens. Model
    output can contain them for legitimate teaching concepts such as an
    unreachable shortest-path distance, so retain the meaning as displayable
    strings instead of silently replacing the value with zero or dropping it.
    """
    if isinstance(value, float) and not math.isfinite(value):
        if math.isnan(value):
            return "NaN"
        return "∞" if value > 0 else "-∞"
    if isinstance(value, Mapping):
        return {str(key): normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_json_value(item) for item in value]
    return value
