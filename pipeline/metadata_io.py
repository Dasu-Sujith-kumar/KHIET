"""Read/write helpers for pipeline metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def validate_metadata(metadata: dict[str, Any]) -> None:
    """Basic schema validation for pipeline metadata."""

    required = [
        "version",
        "profile",
        "threat_level",
        "salt_b64",
        "dtype",
        "working_shape",
        "chaos_seed",
        "metadata_hmac",
    ]
    missing = [field for field in required if field not in metadata]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Metadata missing required fields: {joined}")


def write_metadata(metadata_path: str, metadata: dict[str, Any]) -> None:
    validate_metadata(metadata)
    path = Path(metadata_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(metadata, fh, ensure_ascii=True, indent=2, sort_keys=True)


def read_metadata(metadata_path: str) -> dict[str, Any]:
    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as fh:
        metadata = json.load(fh)
    validate_metadata(metadata)
    return metadata
