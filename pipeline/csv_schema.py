"""
Shared CSV schema for exporting study data.
"""

from typing import Dict, Optional

FIELDNAMES = [
    "nct_id",
    "source",
    "source_url",
    "category",
    "evidence_tier",
    "title",
    "headline",
    "summary",
    "intervention",
    "intervention_description",
    "comparator",
    "population",
    "conditions",
    "sample_size",
    "study_enrollment",
    "sample_size_category",
    "num_arms",
    "completion_date",
    "outcome_name",
    "outcome_type",
    "control_mean",
    "control_sd",
    "control_n",
    "treatment_mean",
    "treatment_sd",
    "treatment_n",
    "ate",
    "effect_size",
    "effect_magnitude",
    "p_value",
    "ultra_score",
]


def calculate_ate(control_mean: Optional[float], treatment_mean: Optional[float]) -> Optional[float]:
    """Compute average treatment effect when both means exist."""
    if control_mean is None or treatment_mean is None:
        return None
    try:
        return float(treatment_mean) - float(control_mean)
    except (TypeError, ValueError):
        return None


def normalize_row(row: Dict) -> Dict:
    """Ensure a row has all fields in FIELDNAMES."""
    return {field: row.get(field, "") for field in FIELDNAMES}
