"""
Comprehensive unit tests for ML utilities: feature engineering, risk thresholds, and leakage guards.
Tests cover boundary conditions, edge cases, and absence of data leakage.
"""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from ml_utils import (
    add_pre_execution_features,
    assert_no_leakage,
    classify_risk,
    normalise_field_name,
    ordinal_encode,
    planned_duration_days,
    workload_hours_per_day,
)


class RiskTierTests(unittest.TestCase):
    """Test risk tier classification for probability thresholds."""
    
    def test_zero_probability_is_low(self):
        self.assertEqual(classify_risk(0), "LOW")

    def test_low_upper_boundary_is_low(self):
        self.assertEqual(classify_risk(0.3999), "LOW")

    def test_medium_lower_boundary_is_medium(self):
        self.assertEqual(classify_risk(0.40), "MEDIUM")

    def test_medium_upper_boundary_is_medium(self):
        self.assertEqual(classify_risk(0.6999), "MEDIUM")

    def test_high_lower_boundary_is_high(self):
        self.assertEqual(classify_risk(0.70), "HIGH")

    def test_one_probability_is_high(self):
        self.assertEqual(classify_risk(1.0), "HIGH")

    def test_invalid_probability_above_one(self):
        with self.assertRaises(ValueError):
            classify_risk(1.01)

    def test_invalid_probability_below_zero(self):
        with self.assertRaises(ValueError):
            classify_risk(-0.1)

    def test_string_probability_is_coerced_to_float(self):
        self.assertEqual(classify_risk("0.5"), "MEDIUM")

    def test_mid_range_probabilities_are_classified_correctly(self):
        self.assertEqual(classify_risk(0.5), "MEDIUM")
        self.assertEqual(classify_risk(0.85), "HIGH")


class LeakageGuardTests(unittest.TestCase):
    """Test that post-outcome fields are rejected as features."""
    
    def test_valid_pre_execution_features_pass(self):
        assert_no_leakage(["priority_enc", "risk_enc", "Hours", "planned_duration"])

    def test_root_cause_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "RootCause"):
            assert_no_leakage(["Hours", "RootCause"])

    def test_actual_date_is_rejected_after_normalisation(self):
        with self.assertRaises(ValueError):
            assert_no_leakage(["Actual Date"])

    def test_delay_is_rejected(self):
        with self.assertRaises(ValueError):
            assert_no_leakage(["Delay"])

    def test_overdue_is_rejected(self):
        with self.assertRaises(ValueError):
            assert_no_leakage(["Overdue"])

    def test_actual_delayed_is_rejected(self):
        with self.assertRaises(ValueError):
            assert_no_leakage(["ActualDelayed"])

    def test_comments_is_rejected(self):
        with self.assertRaises(ValueError):
            assert_no_leakage(["Comments"])

    def test_empty_feature_list_passes(self):
        assert_no_leakage([])

    def test_field_normalisation_is_stable(self):
        self.assertEqual(normalise_field_name("Delay Probability"), "delayprobability")

    def test_normalisation_removes_whitespace_and_symbols(self):
        self.assertEqual(normalise_field_name("Root-Cause_Analysis"), "rootcauseanalysis")


class FeatureEngineeringTests(unittest.TestCase):
    """Test feature transformations for robustness and correctness."""
    
    def test_unknown_ordinal_defaults_to_medium(self):
        self.assertEqual(ordinal_encode(pd.Series(["Unexpected"])).iloc[0], 1)

    def test_ordinal_encode_maps_high_priority(self):
        self.assertEqual(ordinal_encode(pd.Series(["High"])).iloc[0], 2)

    def test_ordinal_encode_maps_low_priority(self):
        self.assertEqual(ordinal_encode(pd.Series(["Low"])).iloc[0], 0)

    def test_ordinal_encode_handles_missing_values(self):
        result = ordinal_encode(pd.Series([None, "High", np.nan, "Low"]))
        self.assertEqual(result.iloc[0], 1)  # NaN defaults to 1
        self.assertEqual(result.iloc[1], 2)  # High
        self.assertEqual(result.iloc[2], 1)  # NaN defaults to 1
        self.assertEqual(result.iloc[3], 0)  # Low

    def test_duration_is_never_less_than_one_day(self):
        duration = planned_duration_days(pd.Series(["2025-01-10"]), pd.Series(["2025-01-09"]))
        self.assertEqual(duration.iloc[0], 1)

    def test_duration_calculates_positive_range(self):
        duration = planned_duration_days(pd.Series(["2025-01-01"]), pd.Series(["2025-01-11"]))
        self.assertEqual(duration.iloc[0], 10)

    def test_duration_handles_invalid_dates(self):
        duration = planned_duration_days(pd.Series(["invalid"]), pd.Series(["also-invalid"]))
        self.assertEqual(duration.iloc[0], 1)  # Fallback to 1

    def test_workload_hours_per_day_calculates_correctly(self):
        result = workload_hours_per_day(pd.Series([80]), pd.Series([10]))
        self.assertEqual(result.iloc[0], 8)

    def test_workload_handles_zero_duration(self):
        result = workload_hours_per_day(pd.Series([100]), pd.Series([0]))
        self.assertEqual(result.iloc[0], 100)  # Zero duration is replaced with 1

    def test_workload_handles_missing_hours(self):
        result = workload_hours_per_day(pd.Series([None, 50]), pd.Series([10, 5]))
        self.assertGreaterEqual(result.iloc[0], 0)  # Falls back to median

    def test_add_pre_execution_features_creates_interaction_term(self):
        source = pd.DataFrame({
            "Priority": ["High"], 
            "Risk": ["High"], 
            "Hours": [40], 
            "Created": ["2025-01-01"], 
            "Target": ["2025-01-05"]
        })
        result = add_pre_execution_features(source)
        self.assertEqual(result.loc[0, "high_pri_high_risk"], 1)

    def test_add_pre_execution_features_does_not_create_interaction_when_only_one_high(self):
        source = pd.DataFrame({
            "Priority": ["High"], 
            "Risk": ["Low"], 
            "Hours": [40], 
            "Created": ["2025-01-01"], 
            "Target": ["2025-01-05"]
        })
        result = add_pre_execution_features(source)
        self.assertEqual(result.loc[0, "high_pri_high_risk"], 0)

    def test_add_pre_execution_features_computes_planned_duration(self):
        source = pd.DataFrame({
            "Priority": ["Medium"], 
            "Risk": ["Medium"], 
            "Hours": [40], 
            "Created": ["2025-01-01"], 
            "Target": ["2025-01-05"]
        })
        result = add_pre_execution_features(source)
        self.assertEqual(result.loc[0, "planned_duration"], 4)

    def test_add_pre_execution_features_does_not_mutate_input(self):
        source = pd.DataFrame({
            "Priority": ["High"], 
            "Risk": ["High"], 
            "Hours": [40], 
            "Created": ["2025-01-01"], 
            "Target": ["2025-01-05"]
        })
        result = add_pre_execution_features(source)
        self.assertNotIn("priority_enc", source.columns)
        self.assertIn("priority_enc", result.columns)

    def test_add_pre_execution_features_raises_on_missing_columns(self):
        source = pd.DataFrame({"Priority": ["High"], "Risk": ["High"]})
        with self.assertRaises(ValueError):
            add_pre_execution_features(source)

    def test_add_pre_execution_features_handles_hours_median_fallback(self):
        source = pd.DataFrame({
            "Priority": ["Medium", "Medium", "Medium"], 
            "Risk": ["Medium", "Medium", "Medium"], 
            "Hours": [None, 40, 50], 
            "Created": ["2025-01-01", "2025-01-01", "2025-01-01"], 
            "Target": ["2025-01-05", "2025-01-05", "2025-01-05"]
        })
        result = add_pre_execution_features(source)
        self.assertEqual(result.loc[0, "Hours"], 45)  # Median of 40, 50


class ConfidenceIntervalTests(unittest.TestCase):
    """Test confidence interval calculations for model metrics."""
    
    def test_wilson_ci_lower_bound_at_0_percent(self):
        """At 0/100, lower confidence bound should be very close to 0."""
        from scipy import stats
        successes, total = 0, 100
        ci = compute_wilson_ci(successes, total, confidence=0.95)
        self.assertGreaterEqual(ci[0], 0)
        self.assertLess(ci[0], 0.05)

    def test_wilson_ci_upper_bound_at_100_percent(self):
        """At 100/100, upper confidence bound should be very close to 1."""
        from scipy import stats
        successes, total = 100, 100
        ci = compute_wilson_ci(successes, total, confidence=0.95)
        self.assertGreater(ci[1], 0.95)
        self.assertLessEqual(ci[1], 1.0)

    def test_wilson_ci_50_percent(self):
        """At 50/100, CI should be roughly symmetric around 0.5."""
        successes, total = 50, 100
        ci = compute_wilson_ci(successes, total, confidence=0.95)
        mid = (ci[0] + ci[1]) / 2
        self.assertAlmostEqual(mid, 0.5, delta=0.05)

    def test_bootstrap_ci_validity(self):
        """Bootstrap CI should contain the sample mean."""
        from scipy import stats
        predictions = np.array([1, 1, 0, 1, 0, 1, 1, 0, 1, 1])  # 70% correct
        ci = compute_bootstrap_ci(predictions, confidence=0.95)
        sample_mean = predictions.mean()
        self.assertLess(ci[0], sample_mean)
        self.assertGreater(ci[1], sample_mean)


def compute_wilson_ci(successes, total, confidence=0.95):
    """
    Compute Wilson score interval for a binary proportion.
    Returns (lower_bound, upper_bound).
    """
    from scipy import stats
    if total == 0:
        return (0, 0)
    p = successes / total
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    margin = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator
    return (max(0, center - margin), min(1, center + margin))


def compute_bootstrap_ci(predictions, confidence=0.95, n_resamples=1000):
    """
    Compute bootstrap confidence interval for accuracy.
    predictions: binary array where 1=correct, 0=incorrect.
    Returns (lower_bound, upper_bound).
    """
    np.random.seed(42)
    bootstrap_means = []
    for _ in range(n_resamples):
        sample = np.random.choice(predictions, size=len(predictions), replace=True)
        bootstrap_means.append(sample.mean())
    alpha = 1 - confidence
    lower = np.percentile(bootstrap_means, (alpha / 2) * 100)
    upper = np.percentile(bootstrap_means, (1 - alpha / 2) * 100)
    return (lower, upper)


if __name__ == "__main__":
    unittest.main()
