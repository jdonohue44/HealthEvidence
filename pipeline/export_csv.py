"""
CSV export module for ultra-significant trials.

This module exports analyzed trial data to CSV format suitable for
the frontend display, including plain-language summaries.
"""

import csv
import os
from datetime import datetime
from typing import List, Dict, Optional
from results_analysis import run_analysis
from categories import get_category_display_name
from scoring import sample_size_descriptor


def generate_headline(study: Dict, outcome: Dict) -> str:
    """
    Generate a plain-language headline for a study finding.
    
    Args:
        study: Study metadata dictionary
        outcome: Outcome data dictionary
        
    Returns:
        Human-readable headline string
    """
    intervention = study["metadata"].get("intervention_names", "The intervention")
    outcome_name = outcome.get("outcome_name", "the outcome")
    
    # Determine direction of effect
    treatment_mean = outcome.get("treatment_mean", 0)
    control_mean = outcome.get("control_mean", 0)
    
    if treatment_mean is None or control_mean is None:
        direction = "affected"
    elif treatment_mean > control_mean:
        direction = "increased"
    else:
        direction = "reduced"
    
    # Calculate absolute difference
    if treatment_mean is not None and control_mean is not None:
        diff = abs(treatment_mean - control_mean)
        diff_str = f" by {diff:.1f}" if diff > 0.1 else ""
    else:
        diff_str = ""
    
    # Shorten intervention name if too long
    if len(intervention) > 60:
        intervention = intervention[:57] + "..."
    
    # Shorten outcome name if too long
    if len(outcome_name) > 50:
        outcome_name = outcome_name[:47] + "..."
    
    headline = f"{intervention} {direction} {outcome_name.lower()}{diff_str}"
    
    return headline


def generate_plain_summary(study: Dict, outcome: Dict) -> str:
    """
    Generate a plain-language summary explaining the finding.
    
    Written for a general audience without scientific jargon.
    
    Args:
        study: Study metadata dictionary
        outcome: Outcome data dictionary
        
    Returns:
        Multi-sentence summary string
    """
    metadata = study["metadata"]
    
    # Get sample sizes
    control_n = outcome.get("control_n", 0) or 0
    treatment_n = outcome.get("treatment_n", 0) or 0
    total_n = int(control_n + treatment_n)
    
    # Get intervention
    intervention = metadata.get("intervention_names", "the treatment")
    if len(intervention) > 80:
        intervention = intervention[:77] + "..."
    
    # Get comparator
    comparator = outcome.get("control_group", "a control group")
    if "placebo" in comparator.lower():
        comparator = "a placebo"
    elif "control" in comparator.lower():
        comparator = "a control group"
    elif "usual" in comparator.lower() or "standard" in comparator.lower():
        comparator = "usual care"
    
    # Get population
    population = metadata.get("population", "participants")
    
    # Get outcome
    outcome_name = outcome.get("outcome_name", "the measured outcome")
    
    # Get effect details
    treatment_mean = outcome.get("treatment_mean")
    control_mean = outcome.get("control_mean")
    effect_size = outcome.get("effect_size")
    effect_mag = outcome.get("effect_magnitude", "")
    
    # Get sample size descriptor for context
    size_desc = sample_size_descriptor(total_n)
    
    # Build the summary
    sentences = []
    
    # First sentence: what researchers did (emphasize sample size for large studies)
    if total_n >= 500:
        sentences.append(
            f"In this large trial, researchers randomly assigned {total_n} {population} to receive either {intervention} or {comparator}."
        )
    elif total_n >= 200:
        sentences.append(
            f"Researchers randomly assigned {total_n} {population} to receive either {intervention} or {comparator}."
        )
    else:
        sentences.append(
            f"Researchers randomly assigned {total_n} {population} to receive either {intervention} or {comparator}."
        )
    
    # Second sentence: what they found
    if treatment_mean is not None and control_mean is not None:
        diff = treatment_mean - control_mean
        if diff > 0:
            direction = "higher"
        else:
            direction = "lower"
        sentences.append(
            f"Those receiving the treatment had {direction} {outcome_name.lower()} on average."
        )
    
    # Third sentence: why this is strong evidence (vary based on sample size)
    if total_n >= 500:
        sentences.append(
            "This is strong evidence because participants were randomly assigned to groups and the large sample size provides reliable estimates."
        )
    else:
        sentences.append(
            "This is strong evidence because participants were randomly assigned to groups, which helps rule out other explanations for the difference."
        )
    
    return " ".join(sentences)


def export_to_csv(results: List[Dict], output_path: str, min_score: float = 0) -> int:
    """
    Export analyzed results to CSV.
    
    Args:
        results: List of analyzed study results
        output_path: Path to output CSV file
        min_score: Minimum ultra-significance score to include (0 = all)
        
    Returns:
        Number of rows exported
    """
    rows = []
    
    for study in results:
        metadata = study["metadata"]
        category = study["category"]
        
        for outcome in study["outcomes"]:
            # Filter by score if specified
            if min_score > 0 and outcome.get("ultra_score", 0) < min_score:
                continue
            
            # Generate plain-language content
            headline = generate_headline(study, outcome)
            summary = generate_plain_summary(study, outcome)
            
            # Calculate total sample size
            control_n = outcome.get("control_n") or 0
            treatment_n = outcome.get("treatment_n") or 0
            total_n = int(control_n + treatment_n)
            
            # Get study-level enrollment (may differ from outcome-level sample sizes)
            study_enrollment = metadata.get("enrollment") or total_n
            
            row = {
                "nct_id": metadata.get("nct_id", ""),
                "category": category,
                "evidence_tier": outcome.get("evidence_tier", "BRONZE"),
                "title": metadata.get("title", ""),
                "headline": headline,
                "summary": summary,
                "intervention": metadata.get("intervention_names", ""),
                "intervention_description": metadata.get("intervention_description", ""),
                "comparator": outcome.get("control_group", ""),
                "population": metadata.get("population", ""),
                "conditions": metadata.get("conditions", ""),
                "sample_size": total_n,
                "study_enrollment": int(study_enrollment) if study_enrollment else total_n,
                "sample_size_category": sample_size_descriptor(total_n),
                "num_arms": metadata.get("num_arms", 2),
                "completion_date": metadata.get("completion_date", ""),
                "outcome_name": outcome.get("outcome_name", ""),
                "outcome_type": outcome.get("outcome_type", ""),
                "control_mean": outcome.get("control_mean"),
                "control_sd": outcome.get("control_sd"),
                "control_n": outcome.get("control_n"),
                "treatment_mean": outcome.get("treatment_mean"),
                "treatment_sd": outcome.get("treatment_sd"),
                "treatment_n": outcome.get("treatment_n"),
                "effect_size": outcome.get("effect_size"),
                "effect_magnitude": outcome.get("effect_magnitude", ""),
                "p_value": outcome.get("p_value"),
                "ultra_score": outcome.get("ultra_score", 0),
            }
            
            rows.append(row)
    
    # Sort by ultra_score descending
    rows.sort(key=lambda x: x.get("ultra_score", 0), reverse=True)
    
    # Write CSV
    if rows:
        fieldnames = list(rows[0].keys())
        
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"Exported {len(rows)} rows to {output_path}")
    else:
        print("No rows to export")
    
    return len(rows)


def run_export(output_path: str = "../frontend/data/trials.csv", max_studies: int = 50):
    """
    Run the full analysis and export pipeline.
    
    Args:
        output_path: Path to output CSV file
        max_studies: Maximum number of studies to analyze
    """
    print("="*60)
    print("ULTRA-SIGNIFICANT TRIALS EXPORT")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Run analysis
    results = run_analysis(max_studies=max_studies)
    
    # Export all results (including non-ultra-significant for completeness)
    total_exported = export_to_csv(results, output_path, min_score=0)
    
    # Also export just the ultra-significant ones
    ultra_path = output_path.replace(".csv", "_ultra.csv")
    ultra_exported = export_to_csv(results, ultra_path, min_score=0.1)
    
    print("\n" + "="*60)
    print("EXPORT COMPLETE")
    print(f"Total findings exported: {total_exported}")
    print(f"Ultra-significant findings: {ultra_exported}")
    print(f"Output: {output_path}")
    print("="*60)


if __name__ == "__main__":
    run_export(max_studies=30)
