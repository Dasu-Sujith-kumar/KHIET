"""Adaptive security profile selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecurityProfile:
    """Runtime parameters for adaptive encryption."""

    name: str
    permutation_rounds: int
    arnold_iterations: int
    description: str


_PROFILE_BY_NAME = {
    "lite": SecurityProfile(
        name="lite",
        permutation_rounds=1,
        arnold_iterations=0,
        description="Fast profile with minimal chaos transforms.",
    ),
    "standard": SecurityProfile(
        name="standard",
        permutation_rounds=2,
        arnold_iterations=3,
        description="Balanced security/performance profile.",
    ),
    "max": SecurityProfile(
        name="max",
        permutation_rounds=3,
        arnold_iterations=7,
        description="Hardened profile for high-risk inputs.",
    ),
}


def select_security_profile(
    sensitivity_label: str,
    threat_level: str = "balanced",
    forced_profile: str | None = None,
) -> SecurityProfile:
    """
    Choose a profile based on sensitivity + threat level, unless forced.

    Parameters
    ----------
    sensitivity_label:
        One of: ``low``, ``medium``, ``high``.
    threat_level:
        One of: ``speed``, ``balanced``, ``hardened``.
    forced_profile:
        Optional explicit profile: ``lite``, ``standard``, or ``max``.
    """

    if forced_profile:
        key = forced_profile.strip().lower()
        if key not in _PROFILE_BY_NAME:
            valid = ", ".join(sorted(_PROFILE_BY_NAME))
            raise ValueError(f"Unknown forced profile '{forced_profile}'. Expected: {valid}.")
        return _PROFILE_BY_NAME[key]

    sensitivity = (sensitivity_label or "medium").strip().lower()
    threat = (threat_level or "balanced").strip().lower()

    if threat not in {"speed", "balanced", "hardened"}:
        raise ValueError("threat_level must be one of: speed, balanced, hardened.")

    if threat == "speed":
        return _PROFILE_BY_NAME["lite"]
    if threat == "hardened":
        return _PROFILE_BY_NAME["max"]

    # balanced
    if sensitivity == "high":
        return _PROFILE_BY_NAME["max"]
    if sensitivity == "low":
        return _PROFILE_BY_NAME["lite"]
    return _PROFILE_BY_NAME["standard"]
