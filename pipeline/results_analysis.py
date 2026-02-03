"""
Enhanced script to analyze results from completed RCTs retrieved from ClinicalTrials.gov.

This script queries the ClinicalTrials.gov API for completed randomized controlled
trials (RCTs) in health, nutrition, and exercise domains from 2020-2026.

It extracts outcome measures, calculates effect sizes, scores trials for
ultra-significance, and assigns categories for the frontend display.
"""

import requests
import math
import time
from typing import Optional, Dict, List, Any
from scoring import cohens_d, effect_magnitude, ultra_significance_score, determine_evidence_tier, sample_size_descriptor
from categories import assign_category

BASE_URL = "https://clinicaltrials.gov/api/v2"

# Query for health/nutrition/exercise RCTs from 2020-2026
QUERY = """
AREA[StudyType]INTERVENTIONAL AND
AREA[DesignAllocation]RANDOMIZED AND
AREA[OverallStatus]COMPLETED AND
AREA[HasResults]true AND
AREA[OutcomeMeasureReportingStatus]POSTED AND
AREA[CompletionDate]RANGE[01/01/2020,12/31/2026] AND
(AREA[ConditionSearch](obesity OR diabetes OR cardiovascular OR hypertension OR 
nutrition OR diet OR exercise OR "physical activity" OR "weight loss" OR 
cholesterol OR "blood pressure" OR fitness OR metabolic))
"""


def safe_float(value) -> Optional[float]:
    """Safely convert a value to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_pvalue(p_value) -> Optional[float]:
    """
    Parse p-value from various formats.
    
    Handles strings like "<0.001", "0.05", etc.
    Returns numeric value suitable for scoring.
    """
    if p_value is None:
        return None
    
    if isinstance(p_value, (int, float)):
        return float(p_value)
    
    if isinstance(p_value, str):
        p_value = p_value.strip()
        
        # Handle "<" prefix (e.g., "<0.001")
        if p_value.startswith('<'):
            try:
                return float(p_value[1:].strip())
            except ValueError:
                return None
        
        # Handle ">" prefix
        if p_value.startswith('>'):
            try:
                return float(p_value[1:].strip())
            except ValueError:
                return None
        
        # Direct numeric string
        try:
            return float(p_value)
        except ValueError:
            return None
    
    return None


def fetch_studies(page_size: int = 100, max_pages: int = 10) -> List[Dict]:
    """
    Fetch studies from ClinicalTrials.gov API with pagination.
    
    Args:
        page_size: Number of studies per page
        max_pages: Maximum number of pages to fetch
        
    Returns:
        List of study dictionaries
    """
    all_studies = []
    next_page_token = None
    
    for page in range(max_pages):
        params = {
            "query.term": QUERY,
            "pageSize": page_size,
            "fields": "NCTId,BriefTitle,Condition,InterventionName,CompletionDate,EnrollmentCount,BriefSummary"
        }
        
        if next_page_token:
            params["pageToken"] = next_page_token
        
        try:
            response = requests.get(f"{BASE_URL}/studies", params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"Error fetching studies (page {page + 1}): {e}")
            break
        
        studies = data.get("studies", [])
        if not studies:
            break
        
        all_studies.extend(studies)
        print(f"Fetched page {page + 1}: {len(studies)} studies (total: {len(all_studies)})")
        
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break
        
        # Be respectful to the API
        time.sleep(0.5)
    
    return all_studies


def fetch_study_details(nct_id: str) -> Optional[Dict]:
    """
    Fetch detailed study data including results.
    
    Args:
        nct_id: The NCT identifier
        
    Returns:
        Full study data dictionary, or None on error
    """
    try:
        response = requests.get(f"{BASE_URL}/studies/{nct_id}", timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching details for {nct_id}: {e}")
        return None


def extract_study_metadata(study_data: Dict) -> Dict:
    """
    Extract metadata from study data.
    
    Args:
        study_data: Full study data from API
        
    Returns:
        Dictionary with extracted metadata
    """
    protocol = study_data.get("protocolSection", {})
    identification = protocol.get("identificationModule", {})
    description = protocol.get("descriptionModule", {})
    design = protocol.get("designModule", {})
    arms = protocol.get("armsInterventionsModule", {})
    eligibility = protocol.get("eligibilityModule", {})
    status = protocol.get("statusModule", {})
    
    # Get intervention descriptions
    interventions = arms.get("interventions", [])
    intervention_names = [i.get("name", "") for i in interventions]
    intervention_desc = "; ".join([i.get("description", "") for i in interventions if i.get("description")])
    
    # Get arm/group count for context
    arm_groups = arms.get("armGroups", [])
    num_arms = len(arm_groups)
    
    # Get conditions
    conditions = protocol.get("conditionsModule", {})
    condition_list = conditions.get("conditions", [])
    
    # Get enrollment from enrollmentInfo - this is the total study enrollment
    enrollment_info = design.get("enrollmentInfo", {})
    enrollment = safe_float(enrollment_info.get("count"))
    enrollment_type = enrollment_info.get("type", "")  # ACTUAL or ESTIMATED
    
    # Get completion date
    completion = status.get("completionDateStruct", {})
    completion_date = completion.get("date", "")
    
    # Get eligibility criteria
    eligibility_criteria = eligibility.get("eligibilityCriteria", "")
    min_age = eligibility.get("minimumAge", "")
    max_age = eligibility.get("maximumAge", "")
    sex = eligibility.get("sex", "")
    
    # Build population description
    population_parts = []
    if min_age or max_age:
        if min_age and max_age:
            population_parts.append(f"ages {min_age} to {max_age}")
        elif min_age:
            population_parts.append(f"ages {min_age} and older")
        elif max_age:
            population_parts.append(f"ages up to {max_age}")
    if condition_list:
        population_parts.append(f"with {', '.join(condition_list[:2])}")
    
    population = ", ".join(population_parts) if population_parts else "adults"
    
    return {
        "nct_id": identification.get("nctId", ""),
        "title": identification.get("briefTitle", ""),
        "brief_summary": description.get("briefSummary", ""),
        "intervention_names": ", ".join(intervention_names),
        "intervention_description": intervention_desc,
        "conditions": ", ".join(condition_list),
        "population": population,
        "enrollment": enrollment,
        "enrollment_type": enrollment_type,
        "num_arms": num_arms,
        "completion_date": completion_date,
    }


def extract_outcomes(study_data: Dict) -> List[Dict]:
    """
    Extract outcome measures with statistics from study results.
    
    Args:
        study_data: Full study data from API
        
    Returns:
        List of outcome dictionaries with statistics
    """
    results = study_data.get("resultsSection", {})
    outcomes_module = results.get("outcomeMeasuresModule", {})
    outcome_measures = outcomes_module.get("outcomeMeasures", [])
    
    extracted = []
    
    for outcome in outcome_measures:
        outcome_type = outcome.get("type", "").upper()
        outcome_title = outcome.get("title", "")
        outcome_description = outcome.get("description", "")
        
        # Get groups
        groups = {g["id"]: g["title"] for g in outcome.get("groups", [])}
        
        # Identify control vs treatment groups
        control_id = None
        for gid, title in groups.items():
            title_lower = title.lower()
            if any(term in title_lower for term in ["control", "placebo", "usual care", "standard", "sham"]):
                control_id = gid
                break
        
        if not control_id:
            continue
        
        treatment_ids = [gid for gid in groups if gid != control_id]
        if not treatment_ids:
            continue
        
        # Get denominators (sample sizes)
        denoms = {}
        for denom in outcome.get("denoms", []):
            for count in denom.get("counts", []):
                gid = count.get("groupId")
                value = safe_float(count.get("value"))
                if gid and value:
                    denoms[gid] = value
        
        # Get measurements (means and dispersions)
        stats = {}
        for cls in outcome.get("classes", []):
            for cat in cls.get("categories", []):
                for measurement in cat.get("measurements", []):
                    gid = measurement.get("groupId")
                    mean = safe_float(measurement.get("value"))
                    
                    if gid is None or mean is None:
                        continue
                    
                    # Get standard deviation
                    sd = None
                    if "dispersionValue" in measurement:
                        sd = safe_float(measurement.get("dispersionValue"))
                    elif "upperLimit" in measurement and "lowerLimit" in measurement:
                        upper = safe_float(measurement.get("upperLimit"))
                        lower = safe_float(measurement.get("lowerLimit"))
                        if upper is not None and lower is not None:
                            # Approximate SD from confidence interval
                            sd = (upper - lower) / 4.0
                    
                    stats[gid] = {"mean": mean, "sd": sd}
        
        if control_id not in stats:
            continue
        
        # Get p-value from analyses
        p_value = None
        for analysis in outcome.get("analyses", []):
            analysis_groups = set(analysis.get("groupIds", []))
            if control_id in analysis_groups and any(tid in analysis_groups for tid in treatment_ids):
                p_value = parse_pvalue(analysis.get("pValue"))
                if p_value is not None:
                    break
        
        # Process each treatment group
        for tid in treatment_ids:
            if tid not in stats:
                continue
            
            control_stats = stats[control_id]
            treatment_stats = stats[tid]
            
            control_n = denoms.get(control_id)
            treatment_n = denoms.get(tid)
            
            # Calculate effect size if we have SDs
            effect_d = None
            if all([control_stats.get("sd"), treatment_stats.get("sd"), control_n, treatment_n]):
                effect_d = cohens_d(
                    mean_treatment=treatment_stats["mean"],
                    mean_control=control_stats["mean"],
                    sd_treatment=treatment_stats["sd"],
                    sd_control=control_stats["sd"],
                    n_treatment=treatment_n,
                    n_control=control_n
                )
            
            # Calculate p-value if not reported and we have the data
            calculated_p = p_value
            if calculated_p is None and all([
                control_stats.get("sd"), treatment_stats.get("sd"),
                control_n, treatment_n
            ]):
                from scipy.stats import ttest_ind_from_stats
                try:
                    _, calculated_p = ttest_ind_from_stats(
                        mean1=treatment_stats["mean"],
                        std1=treatment_stats["sd"],
                        nobs1=treatment_n,
                        mean2=control_stats["mean"],
                        std2=control_stats["sd"],
                        nobs2=control_n,
                        equal_var=False
                    )
                except Exception:
                    pass
            
            total_n = (control_n or 0) + (treatment_n or 0)
            
            # Calculate ultra-significance score
            score = ultra_significance_score(calculated_p, effect_d, total_n)
            
            # Determine evidence tier (now includes sample size requirement)
            tier = determine_evidence_tier(calculated_p, effect_d, sample_size=total_n, is_rct=True)
            
            extracted.append({
                "outcome_type": outcome_type,
                "outcome_name": outcome_title,
                "outcome_description": outcome_description,
                "control_group": groups.get(control_id, ""),
                "treatment_group": groups.get(tid, ""),
                "control_mean": control_stats["mean"],
                "control_sd": control_stats.get("sd"),
                "control_n": control_n,
                "treatment_mean": treatment_stats["mean"],
                "treatment_sd": treatment_stats.get("sd"),
                "treatment_n": treatment_n,
                "p_value": calculated_p,
                "effect_size": effect_d,
                "effect_magnitude": effect_magnitude(effect_d),
                "ultra_score": score,
                "evidence_tier": tier,
            })
    
    return extracted


def analyze_study(nct_id: str) -> Optional[Dict]:
    """
    Analyze a single study and return structured data.
    
    Args:
        nct_id: The NCT identifier
        
    Returns:
        Dictionary with study metadata and outcomes, or None
    """
    study_data = fetch_study_details(nct_id)
    if not study_data:
        return None
    
    metadata = extract_study_metadata(study_data)
    outcomes = extract_outcomes(study_data)
    
    if not outcomes:
        return None
    
    # Assign category
    category = assign_category(
        metadata.get("intervention_description", "") + " " + metadata.get("intervention_names", ""),
        metadata.get("conditions", "")
    )
    
    return {
        "metadata": metadata,
        "outcomes": outcomes,
        "category": category,
    }


def run_analysis(max_studies: int = 50) -> List[Dict]:
    """
    Run the full analysis pipeline.
    
    Args:
        max_studies: Maximum number of studies to analyze
        
    Returns:
        List of analyzed study results
    """
    print("Fetching studies from ClinicalTrials.gov...")
    studies = fetch_studies(page_size=100, max_pages=5)
    
    print(f"\nFound {len(studies)} studies. Analyzing up to {max_studies}...")
    
    results = []
    analyzed = 0
    
    for study in studies[:max_studies * 2]:  # Fetch extra in case some fail
        if analyzed >= max_studies:
            break
        
        nct_id = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
        if not nct_id:
            continue
        
        print(f"Analyzing {nct_id}...")
        result = analyze_study(nct_id)
        
        if result and result["outcomes"]:
            results.append(result)
            analyzed += 1
            
            # Show progress for high-scoring outcomes
            for outcome in result["outcomes"]:
                if outcome["ultra_score"] > 0:
                    print(f"  Found ultra-significant: {outcome['outcome_name'][:50]} (score: {outcome['ultra_score']:.2f})")
        
        time.sleep(0.3)  # Rate limiting
    
    print(f"\nAnalysis complete. Processed {len(results)} studies with outcomes.")
    return results


if __name__ == "__main__":
    results = run_analysis(max_studies=30)
    
    # Print summary
    print("\n" + "="*60)
    print("ULTRA-SIGNIFICANT FINDINGS SUMMARY")
    print("="*60)
    
    ultra_sig = []
    for study in results:
        for outcome in study["outcomes"]:
            if outcome["ultra_score"] > 0:
                ultra_sig.append({
                    "nct_id": study["metadata"]["nct_id"],
                    "title": study["metadata"]["title"],
                    "category": study["category"],
                    "outcome": outcome["outcome_name"],
                    "score": outcome["ultra_score"],
                    "effect": outcome["effect_size"],
                    "p_value": outcome["p_value"],
                })
    
    # Sort by score
    ultra_sig.sort(key=lambda x: x["score"], reverse=True)
    
    for i, finding in enumerate(ultra_sig[:10], 1):
        print(f"\n{i}. [{finding['category'].upper()}] {finding['title'][:60]}")
        print(f"   Outcome: {finding['outcome'][:50]}")
        print(f"   Effect size: {finding['effect']:.2f if finding['effect'] else 'N/A'}")
        print(f"   p-value: {finding['p_value']:.6f if finding['p_value'] else 'N/A'}")
        print(f"   Ultra-significance score: {finding['score']:.2f}")
