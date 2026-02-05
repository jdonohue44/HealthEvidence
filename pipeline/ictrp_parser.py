"""
ICTRP XML Parser for health studies.

Parses the International Clinical Trials Registry Platform (ICTRP) XML export
to extract completed trials with posted results that match our health topics.
"""

import xml.etree.ElementTree as ET
import re
import csv
from typing import Optional, Dict, List, Any
from pathlib import Path

from csv_schema import FIELDNAMES, normalize_row
from scoring import ultra_significance_score, determine_evidence_tier, effect_magnitude, sample_size_descriptor
from categories import assign_category

# Topic focus - includes controversial/popular health topics
TOPIC_TERMS = [
    # Weight and metabolic
    "obesity", "overweight", "metabolic", "weight loss", "weight gain",
    # Cardiovascular
    "blood pressure", "cholesterol", "lipid", "cardiovascular", "heart",
    # Nutrition basics
    "nutrition", "diet", "dietary", "fiber", "supplement", "vitamin", "probiotic", "omega-3",
    # Controversial foods - eggs, meat, fats
    "egg", "eggs", "red meat", "processed meat", "processed food",
    "saturated fat", "trans fat", "butter", "coconut oil",
    # Sweeteners and sugar
    "sweetener", "artificial sweetener", "aspartame", "sucralose",
    "sugar", "added sugar", "high fructose", "stevia",
    # Salt and sodium
    "salt", "sodium",
    # Beverages
    "coffee", "caffeine", "alcohol", "wine", "energy drink",
    # Supplements and vaccines
    "vaccination", "vaccine", "multivitamin", "fish oil",
    # Exercise and activity
    "physical activity", "exercise", "fitness", "strength",
    "resistance training", "stretching", "yoga", "running", "walking",
    # Sleep and mental health
    "sleep", "insomnia", "stress", "anxiety", "depression",
    "mental health", "well-being",
    # Other health topics
    "inflammation", "gut microbiome", "bone", "bone density",
    "muscle", "frailty", "aging", "longevity", "fasting", "intermittent fasting"
]
TOPIC_PATTERN = re.compile("|".join(re.escape(t) for t in TOPIC_TERMS), re.I)


def get_text(element: Optional[ET.Element], default: str = "") -> str:
    """Safely extract text from an XML element."""
    if element is None:
        return default
    text = element.text
    return text.strip() if text else default


def parse_sample_size(text: str) -> Optional[int]:
    """Extract sample size from target_size field."""
    if not text:
        return None
    # Remove non-numeric characters and try to parse
    cleaned = re.sub(r"[^\d]", "", text)
    if cleaned:
        try:
            n = int(cleaned)
            if 1 <= n <= 1000000:
                return n
        except ValueError:
            pass
    return None


def is_randomized(text: str) -> bool:
    """Check if the study design indicates randomization."""
    if not text:
        return False
    text_lower = text.lower()
    return any(term in text_lower for term in [
        "rct", "randomized", "randomised", "random allocation", 
        "random assignment", "randomly assigned"
    ])


def extract_statistics_from_summary(text: str) -> Dict[str, Any]:
    """
    Extract statistical information from results summary.
    
    Args:
        text: Results summary text
        
    Returns:
        Dictionary with extracted statistics
    """
    stats = {
        "p_values": [],
        "effect_sizes": [],
        "confidence_intervals": []
    }
    
    if not text:
        return stats
    
    # Extract p-values
    p_value_matches = re.findall(
        r"\bp\s*[<=>≤≥]\s*(0\.\d+|\d+e-\d+)",
        text, re.I
    )
    for p in p_value_matches:
        try:
            val = float(p.replace('e', 'E'))
            if 0 < val < 1:
                stats["p_values"].append(val)
        except ValueError:
            pass
    
    # Extract effect sizes (Cohen's d, OR, RR, HR)
    effect_matches = re.findall(
        r"\b(?:d\s*=\s*|OR\s*[=:]\s*|RR\s*[=:]\s*|HR\s*[=:]\s*|"
        r"effect\s*size\s*[=:]\s*)(-?\d+\.?\d*)",
        text, re.I
    )
    stats["effect_sizes"] = [float(e) for e in effect_matches if abs(float(e)) < 50]
    
    # Extract confidence intervals
    ci_matches = re.findall(
        r"95%?\s*CI\s*[=:,]?\s*\[?\(?\s*(-?\d+\.?\d*)\s*[-–,to]+\s*(-?\d+\.?\d*)\s*\]?\)?",
        text, re.I
    )
    stats["confidence_intervals"] = [(float(a), float(b)) for a, b in ci_matches]
    
    return stats


def generate_headline(trial: Dict) -> str:
    """Generate a plain-language headline from the trial title."""
    title = trial.get("title", "")
    
    # Use public title, fall back to scientific title
    if not title or len(title) < 10:
        title = trial.get("scientific_title", "")
    
    # Remove common academic prefixes
    title = re.sub(r"^(A|An|The)\s+", "", title, flags=re.I)
    title = re.sub(r"^(Effect|Effects|Impact|Impacts|Efficacy|Association|Study|Trial)\s+of\s+", "", title, flags=re.I)
    
    # Clean up HTML entities
    title = title.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    title = re.sub(r"<br\s*/?>", " ", title)
    
    # Truncate if too long
    if len(title) > 100:
        title = title[:97] + "..."
    
    return title


def generate_summary(trial: Dict) -> str:
    """Generate a plain-language summary from the trial data."""
    summary = trial.get("results_summary", "")
    
    if summary:
        # Clean up HTML
        summary = summary.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
        summary = re.sub(r"<br\s*/?>", " ", summary)
        # Truncate to reasonable length
        if len(summary) > 500:
            # Try to cut at sentence boundary
            sentences = summary[:500].split(". ")
            summary = ". ".join(sentences[:-1]) + "." if len(sentences) > 1 else summary[:497] + "..."
    else:
        # Generate from other fields
        title = trial.get("title", "")
        sample_size = trial.get("sample_size")
        
        if sample_size:
            summary = f"This trial enrolled {sample_size} participants to study {title.lower()[:50]}."
        else:
            summary = f"This international trial examined {title.lower()[:50]}."
    
    return summary


def parse_trial(trial_elem: ET.Element) -> Optional[Dict]:
    """
    Parse a single Trial element from the ICTRP XML.
    
    Args:
        trial_elem: XML Element for a Trial
        
    Returns:
        Parsed trial dictionary, or None if not suitable
    """
    # Extract basic fields
    trial_id = get_text(trial_elem.find("TrialID"))
    public_title = get_text(trial_elem.find("Public_title"))
    scientific_title = get_text(trial_elem.find("Scientific_title"))
    study_type = get_text(trial_elem.find("Study_type"))
    study_design = get_text(trial_elem.find("Study_design"))
    target_size = get_text(trial_elem.find("Target_size"))
    condition = get_text(trial_elem.find("Condition"))
    intervention = get_text(trial_elem.find("Intervention"))
    primary_outcome = get_text(trial_elem.find("Primary_outcome"))
    secondary_outcome = get_text(trial_elem.find("Secondary_outcome"))
    results_yes_no = get_text(trial_elem.find("results_yes_no"))
    results_summary = get_text(trial_elem.find("results_summary"))
    results_date = get_text(trial_elem.find("results_date_completed"))
    web_address = get_text(trial_elem.find("web_address"))
    source_register = get_text(trial_elem.find("Source_Register"))
    
    # Only process trials with posted results
    if results_yes_no.lower() != "yes":
        return None
    
    # Check if interventional study
    if "interventional" not in study_type.lower():
        return None
    
    # Build full text for topic matching
    full_text = " ".join([
        public_title, scientific_title, condition, intervention,
        primary_outcome, secondary_outcome, results_summary
    ])
    
    # Check if matches our topic criteria
    if not TOPIC_PATTERN.search(full_text):
        return None
    
    # Parse sample size
    sample_size = parse_sample_size(target_size)
    
    # Check if randomized
    is_rct = is_randomized(study_design)
    
    # Extract statistics from results summary
    stats = extract_statistics_from_summary(results_summary)
    
    # Get best p-value and effect size
    best_p = min(stats["p_values"]) if stats["p_values"] else None
    best_effect = max(stats["effect_sizes"], key=abs) if stats["effect_sizes"] else None
    
    # Calculate scores
    ultra_score = 0
    if all([best_p, best_effect, sample_size]):
        ultra_score = ultra_significance_score(best_p, best_effect, sample_size)
    
    evidence_tier = determine_evidence_tier(best_p, best_effect, sample_size, is_rct)
    
    # Assign category
    category = assign_category(intervention, condition)
    
    trial_data = {
        "trial_id": trial_id,
        "source": "ictrp",
        "source_register": source_register,
        "source_url": web_address,
        "title": public_title or scientific_title,
        "scientific_title": scientific_title,
        "study_type": study_type,
        "study_design": study_design,
        "condition": condition,
        "intervention": intervention,
        "primary_outcome": primary_outcome,
        "secondary_outcome": secondary_outcome,
        "sample_size": sample_size,
        "results_summary": results_summary,
        "results_date": results_date,
        "is_rct": is_rct,
        "p_value": best_p,
        "effect_size": best_effect,
        "effect_magnitude": effect_magnitude(best_effect) if best_effect else "",
        "ultra_score": ultra_score,
        "evidence_tier": evidence_tier,
        "category": category,
    }
    
    # Generate headline and summary
    trial_data["headline"] = generate_headline(trial_data)
    trial_data["summary"] = generate_summary(trial_data)
    
    return trial_data


def trial_to_row(trial: Dict) -> Dict:
    """Convert an ICTRP trial record to a CSV row."""
    return {
        "nct_id": trial.get("trial_id", ""),
        "source": trial.get("source", "ictrp"),
        "source_url": trial.get("source_url", ""),
        "category": trial.get("category", "health"),
        "evidence_tier": trial.get("evidence_tier", "BRONZE"),
        "title": trial.get("title", ""),
        "headline": trial.get("headline", ""),
        "summary": trial.get("summary", ""),
        "intervention": trial.get("intervention", "")[:200],  # Truncate long interventions
        "intervention_description": "",
        "comparator": "",
        "population": "",
        "conditions": trial.get("condition", ""),
        "sample_size": trial.get("sample_size") or 0,
        "study_enrollment": trial.get("sample_size") or 0,
        "sample_size_category": sample_size_descriptor(trial.get("sample_size")) if trial.get("sample_size") else "",
        "num_arms": 2,  # Default
        "completion_date": trial.get("results_date", ""),
        "outcome_name": trial.get("primary_outcome", "")[:200],
        "outcome_type": "PRIMARY",
        "control_mean": None,
        "control_sd": None,
        "control_n": None,
        "treatment_mean": None,
        "treatment_sd": None,
        "treatment_n": None,
        "ate": None,
        "effect_size": trial.get("effect_size"),
        "effect_magnitude": trial.get("effect_magnitude", ""),
        "p_value": trial.get("p_value"),
        "ultra_score": trial.get("ultra_score", 0),
    }


def parse_ictrp_xml(xml_path: str, max_trials: int = None) -> List[Dict]:
    """
    Parse the ICTRP XML file and extract relevant trials.
    
    Args:
        xml_path: Path to the ICTRP XML file
        max_trials: Maximum number of trials to process (None for all)
        
    Returns:
        List of parsed trial dictionaries
    """
    print(f"Parsing ICTRP XML from {xml_path}...")
    
    trials = []
    trial_count = 0
    processed_count = 0
    
    # Use iterparse for memory efficiency with large files
    context = ET.iterparse(xml_path, events=("end",))
    
    for event, elem in context:
        if elem.tag == "Trial":
            trial_count += 1
            
            if trial_count % 10000 == 0:
                print(f"  Processed {trial_count} trials, found {len(trials)} matches...")
            
            trial_data = parse_trial(elem)
            if trial_data:
                trials.append(trial_data)
                
                if max_trials and len(trials) >= max_trials:
                    break
            
            # Clear the element to free memory
            elem.clear()
    
    # Sort by ultra_score descending
    trials.sort(key=lambda x: x.get("ultra_score", 0), reverse=True)
    
    print(f"Parsed {trial_count} total trials, found {len(trials)} matching our criteria")
    return trials


def export_to_csv(trials: List[Dict], output_path: str) -> int:
    """
    Export trials to CSV format compatible with the frontend.
    
    Args:
        trials: List of parsed trial dictionaries
        output_path: Path to output CSV file
        
    Returns:
        Number of rows exported
    """
    if not trials:
        print("No trials to export")
        return 0
    
    rows = [normalize_row(trial_to_row(t)) for t in trials]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Exported {len(rows)} rows to {output_path}")
    return len(rows)


if __name__ == "__main__":
    # Default path to ICTRP XML
    xml_path = Path(__file__).parent.parent / "frontend" / "data" / "ICTRP-Results.xml"
    
    if not xml_path.exists():
        print(f"ICTRP XML file not found at {xml_path}")
        exit(1)
    
    # Parse trials (limit to 500 for testing)
    trials = parse_ictrp_xml(str(xml_path), max_trials=500)
    
    # Print summary
    print("\n" + "="*60)
    print("ICTRP PARSER RESULTS")
    print("="*60)
    
    high_quality = [t for t in trials if t["ultra_score"] > 0]
    rcts = [t for t in trials if t["is_rct"]]
    
    print(f"Total matching trials: {len(trials)}")
    print(f"RCTs: {len(rcts)}")
    print(f"High-quality (ultra_score > 0): {len(high_quality)}")
    
    # Show category breakdown
    categories = {}
    for t in trials:
        cat = t.get("category", "health")
        categories[cat] = categories.get(cat, 0) + 1
    print(f"\nBy category: {categories}")
    
    if high_quality:
        print("\nTop findings:")
        for i, t in enumerate(high_quality[:5], 1):
            print(f"\n{i}. [{t['category'].upper()}] {t['headline'][:60]}")
            print(f"   Score: {t['ultra_score']:.2f}, p={t['p_value']}, effect={t['effect_size']}")
            print(f"   Source: {t['source_register']}")
    
    # Export to CSV
    output_path = Path(__file__).parent.parent / "frontend" / "data" / "ictrp_trials.csv"
    export_to_csv(trials, str(output_path))
