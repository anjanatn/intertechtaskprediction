"""Pure, testable helpers for pre-execution delay-risk features."""

from __future__ import annotations

import math
from typing import Iterable

import pandas as pd


RISK_THRESHOLDS = ((0.40, "LOW"), (0.70, "MEDIUM"), (math.inf, "HIGH"))
POST_OUTCOME_FIELDS = {
    "delay", "actual", "actualdate", "rootcause", "overdue", "comments",
    "actualdelayed", "riskcat", "delayscore", "delayprob",
}
PRIORITY_MAP = {"High": 2, "Medium": 1, "Low": 0}


def classify_risk(probability: float) -> str:
    """Return the operational tier for a probability in the inclusive [0, 1] range."""
    probability = float(probability)
    if not 0 <= probability <= 1:
        raise ValueError("probability must be between 0 and 1")
    for upper_bound, tier in RISK_THRESHOLDS:
        if probability < upper_bound:
            return tier
    raise AssertionError("unreachable")


def normalise_field_name(name: str) -> str:
    return "".join(character for character in str(name).lower() if character.isalnum())


def assert_no_leakage(feature_names: Iterable[str]) -> None:
    """Reject fields that are known only after a task outcome has occurred."""
    leaking = [name for name in feature_names if normalise_field_name(name) in POST_OUTCOME_FIELDS]
    if leaking:
        raise ValueError(f"post-outcome leakage fields are not permitted: {', '.join(leaking)}")


def ordinal_encode(values: pd.Series, mapping: dict[str, int] = PRIORITY_MAP) -> pd.Series:
    """Encode project priority/risk values; unknown or absent values default to Medium."""
    return values.map(mapping).fillna(1).astype(int)


def planned_duration_days(created: pd.Series, target: pd.Series) -> pd.Series:
    created_dates = pd.to_datetime(created, errors="coerce")
    target_dates = pd.to_datetime(target, errors="coerce")
    return (target_dates - created_dates).dt.days.fillna(1).clip(lower=1).astype(int)


def workload_hours_per_day(hours: pd.Series, duration_days: pd.Series) -> pd.Series:
    safe_duration = pd.to_numeric(duration_days, errors="coerce").replace(0, 1).fillna(1)
    numeric_hours = pd.to_numeric(hours, errors="coerce")
    fallback = numeric_hours.median()
    numeric_hours = numeric_hours.fillna(0 if pd.isna(fallback) else fallback)
    return numeric_hours / safe_duration


def add_pre_execution_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with only deterministic pre-execution feature-engineering columns."""
    required = {"Priority", "Risk", "Hours", "Created", "Target"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
    result = frame.copy()
    result["Created"] = pd.to_datetime(result["Created"], errors="coerce")
    result["Target"] = pd.to_datetime(result["Target"], errors="coerce")
    result["priority_enc"] = ordinal_encode(result["Priority"])
    result["risk_enc"] = ordinal_encode(result["Risk"])
    result["high_pri_high_risk"] = ((result["priority_enc"] == 2) & (result["risk_enc"] == 2)).astype(int)
    result["planned_duration"] = planned_duration_days(result["Created"], result["Target"])
    result["Hours"] = pd.to_numeric(result["Hours"], errors="coerce")
    result["Hours"] = result["Hours"].fillna(result["Hours"].median()).fillna(0)
    result["hours_per_day"] = workload_hours_per_day(result["Hours"], result["planned_duration"])
    return result
