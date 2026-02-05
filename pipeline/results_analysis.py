"""
Script to analyze results from completed RCTs retrieved from ClinicalTrials.gov.

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

# Topic focus for health/nutrition/exercise trials
# Includes controversial/popular health topics people search for
TOPIC_TERMS = [
    # Weight and metabolic
    "obesity", "overweight", "metabolic", "\"weight loss\"", "\"weight gain\"",
    
    # Cardiovascular
    "\"blood pressure\"", "cholesterol", "lipid", "cardiovascular", "heart",
    
    # Nutrition basics
    "nutrition", "diet", "dietary", "fiber", "supplement", "vitamin", "probiotic", "\"omega-3\"",
    
    # Controversial foods - eggs, meat, fats
    "egg", "eggs", "\"red meat\"", "\"processed meat\"", "\"processed food\"",
    "\"saturated fat\"", "\"trans fat\"", "butter", "\"coconut oil\"",
    
    # Sweeteners and sugar
    "sweetener", "\"artificial sweetener\"", "aspartame", "sucralose",
    "sugar", "\"added sugar\"", "\"high fructose\"", "stevia",
    
    # Salt and sodium
    "salt", "sodium",
    
    # Beverages
    "coffee", "caffeine", "alcohol", "wine", "\"energy drink\"",
    
    # Supplements and vaccines
    "vaccination", "vaccine", "multivitamin", "\"fish oil\"",
    
    # Exercise and activity
    "\"physical activity\"", "exercise", "fitness", "strength",
    "\"resistance training\"", "stretching", "yoga", "running", "walking",
    
    # Sleep and mental health
    "sleep", "insomnia", "stress", "anxiety", "depression", 
    "\"mental health\"", "\"well-being\"",
    
    # Other health topics
    "inflammation", "\"gut microbiome\"", "bone", "\"bone density\"",
    "muscle", "frailty", "aging", "longevity", "fasting", "\"intermittent fasting\""
]
TOPIC_QUERY = " OR ".join(TOPIC_TERMS)

# Query for health/nutrition/exercise RCTs from 2020-2026
QUERY = f"""
AREA[StudyType]INTERVENTIONAL AND
AREA[DesignAllocation]RANDOMIZED AND
AREA[OverallStatus]COMPLETED AND
AREA[HasResults]true AND
AREA[OutcomeMeasureReportingStatus]POSTED AND
AREA[CompletionDate]RANGE[01/01/2020,12/31/2026] AND
(
  AREA[ConditionSearch]({TOPIC_QUERY}) OR
  AREA[BriefTitle]({TOPIC_QUERY}) OR
  AREA[InterventionName]({TOPIC_QUERY})
)
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


def is_mean_param(param_type: Optional[str]) -> bool:
    """Check if the parameter type represents a mean."""
    if not param_type:
        return True
    param = str(param_type).strip().lower()
    if "median" in param:
        return False
    return "mean" in param


def is_baseline_label(label: str) -> bool:
    """Heuristic to detect baseline-only measurements."""
    if not label:
        return False
    label = label.lower()
    return any(term in label for term in ["baseline", "pre-treatment", "pretreatment", "pre treatment", "screening"])


def parse_dispersion_to_sd(measurement: Dict, group_n: Optional[float]) -> Optional[float]:
    """
    Convert dispersion data to a standard deviation when possible.
    """
    dispersion_value = safe_float(measurement.get("dispersionValue"))
    dispersion_type = str(measurement.get("dispersionType") or "").strip().lower()
    sd = None

    if dispersion_value is not None:
        if dispersion_type == "" or "standard deviation" in dispersion_type or dispersion_type in {"sd", "stdev"}:
            sd = dispersion_value
        elif "standard error" in dispersion_type or dispersion_type in {"se", "sem"}:
            if group_n:
                sd = dispersion_value * math.sqrt(group_n)
        elif "confidence interval" in dispersion_type or dispersion_type == "ci":
            sd = None

    upper = safe_float(measurement.get("upperLimit"))
    lower = safe_float(measurement.get("lowerLimit"))
    if sd is None and upper is not None and lower is not None and upper > lower:
        width = upper - lower
        if group_n:
            sd = (width / (2 * 1.96)) * math.sqrt(group_n)
        else:
            sd = width / 4.0

    return sd


def select_analysis_p_value(analyses: List[Dict], control_id: str, treatment_id: str) -> Optional[float]:
    """Pick the most specific analysis p-value for a control-treatment comparison."""
    best_p = None
    best_group_count = None

    for analysis in analyses:
        group_ids = analysis.get("groupIds", [])
        if not group_ids or control_id not in group_ids or treatment_id not in group_ids:
            continue

        p_value = parse_pvalue(analysis.get("pValue"))
        if p_value is None:
            continue

        group_count = len(group_ids)
        if best_p is None or group_count < best_group_count:
            best_p = p_value
            best_group_count = group_count
            if group_count <= 2:
                break

    return best_p


def select_measurement_set(measurement_sets: List[Dict], control_id: str, treatment_id: str,
                           denoms: Dict[str, float]) -> Optional[Dict]:
    """Choose the best measurement set for a given control vs treatment pair."""
    candidates = [s for s in measurement_sets if control_id in s["stats"] and treatment_id in s["stats"]]
    if not candidates:
        return None

    non_baseline = [
        s for s in candidates
        if not is_baseline_label(f"{s.get('class_title', '')} {s.get('category_title', '')}")
    ]
    if non_baseline:
        candidates = non_baseline

    def score(set_data: Dict) -> tuple:
        stats = set_data["stats"]
        sd_count = int(stats[control_id].get("sd") is not None) + int(stats[treatment_id].get("sd") is not None)
        total_n = (denoms.get(control_id) or 0) + (denoms.get(treatment_id) or 0)
        return (sd_count, total_n)

    return max(candidates, key=score)


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

    def valid_sd(value: Optional[float]) -> bool:
        return value is not None and value > 0

    def valid_n(value: Optional[float]) -> bool:
        return value is not None and value > 1

    for outcome in outcome_measures:
        outcome_type = outcome.get("type", "").upper()
        outcome_title = outcome.get("title", "")
        outcome_description = outcome.get("description", "")

        # Get groups
        groups_list = outcome.get("groups", [])
        groups = {g.get("id"): g.get("title", "") for g in groups_list if g.get("id")}

        # Identify control vs treatment groups
        control_id = None
        for group in groups_list:
            group_type = str(group.get("type") or "").lower()
            title_lower = str(group.get("title") or "").lower()
            if "control" in group_type or "placebo" in group_type or "sham" in group_type:
                control_id = group.get("id")
                break
            if not control_id and any(term in title_lower for term in ["control", "placebo", "usual care", "standard", "sham"]):
                control_id = group.get("id")

        if not control_id:
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
                if gid is not None and value is not None:
                    denoms[gid] = value

        # Get measurements (means and dispersions)
        measurement_sets = []
        for cls in outcome.get("classes", []):
            class_title = cls.get("title", "")
            for cat in cls.get("categories", []):
                category_title = cat.get("title", "")
                stats = {}
                for measurement in cat.get("measurements", []):
                    gid = measurement.get("groupId")
                    mean = safe_float(measurement.get("value"))
                    if gid is None or mean is None:
                        continue

                    param_type = measurement.get("paramType") or cat.get("paramType") or cls.get("paramType")
                    if not is_mean_param(param_type):
                        continue

                    group_n = denoms.get(gid)
                    sd = parse_dispersion_to_sd(measurement, group_n)
                    stats[gid] = {"mean": mean, "sd": sd}

                if stats:
                    measurement_sets.append({
                        "class_title": class_title,
                        "category_title": category_title,
                        "stats": stats
                    })

        if not measurement_sets:
            continue

        analyses = outcome.get("analyses", [])

        # Process each treatment group
        for tid in treatment_ids:
            measurement_set = select_measurement_set(measurement_sets, control_id, tid, denoms)
            if not measurement_set:
                continue

            stats = measurement_set["stats"]
            control_stats = stats[control_id]
            treatment_stats = stats[tid]

            control_n = denoms.get(control_id)
            treatment_n = denoms.get(tid)

            # Use the most specific analysis p-value when available
            calculated_p = select_analysis_p_value(analyses, control_id, tid)

            # Calculate effect size if we have SDs
            effect_d = None
            if valid_sd(control_stats.get("sd")) and valid_sd(treatment_stats.get("sd")) and valid_n(control_n) and valid_n(treatment_n):
                effect_d = cohens_d(
                    mean_treatment=treatment_stats["mean"],
                    mean_control=control_stats["mean"],
                    sd_treatment=treatment_stats["sd"],
                    sd_control=control_stats["sd"],
                    n_treatment=treatment_n,
                    n_control=control_n
                )

            # Calculate p-value if not reported and we have the data
            if calculated_p is None and valid_sd(control_stats.get("sd")) and valid_sd(treatment_stats.get("sd")) and valid_n(control_n) and valid_n(treatment_n):
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
        
        nct_id = (
            study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
            or study.get("nctId")
            or study.get("NCTId")
        )
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
