"""
MedRxiv scraper for health studies.

Fetches preprints from medRxiv (the preprint server for health sciences)
that match our topic keywords, extracts statistical information,
and integrates with the scoring pipeline.
"""

import requests
import re
import json
import csv
import datetime as dt
from typing import Optional, Dict, List, Any

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


def fetch_interval(start: str, end: str, server: str = "medrxiv", max_records: Optional[int] = None) -> List[Dict]:
    """
    Fetch preprints from medRxiv API within a date range.
    
    Args:
        start: Start date in YYYY-MM-DD format
        end: End date in YYYY-MM-DD format
        server: 'medrxiv' or 'biorxiv'
        
    Returns:
        List of preprint records
    """
    base_url = "https://api.medrxiv.org/details"
    cursor = 0
    results = []
    
    while True:
        url = f"{base_url}/{server}/{start}/{end}/{cursor}/json"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            batch = response.json().get("collection", [])
            if not batch:
                break
            results.extend(batch)
            cursor += 100
            print(f"  Fetched {len(results)} records...")
            if max_records and len(results) >= max_records:
                break
        except requests.RequestException as e:
            print(f"Error fetching from medRxiv: {e}")
            break
    
    return results


def extract_statistics(text: str) -> Dict[str, Any]:
    """
    Extract statistical information from abstract text.
    
    Args:
        text: Abstract or full text to parse
        
    Returns:
        Dictionary with extracted statistics
    """
    stats = {
        "participants": [],
        "arms": [],
        "p_values": [],
        "effect_sizes": [],
        "confidence_intervals": []
    }
    
    # Extract participant counts (n=X, N=X patterns)
    participant_matches = re.findall(
        r"(?:n\s*=\s*|N\s*=\s*|\bN\s*=?\s*|participants?\s*[=:]\s*|enrolled\s+)(\d{2,5})",
        text
    )
    stats["participants"] = [int(p) for p in participant_matches if 10 <= int(p) <= 100000]
    
    # Extract number of arms
    arm_matches = re.findall(r"(\d+)\s*[-\s]?(?:arm|group|arms|groups)\b", text, re.I)
    stats["arms"] = [int(a) for a in arm_matches if 2 <= int(a) <= 10]
    
    # Extract p-values
    p_value_matches = re.findall(
        r"\bp\s*[<=>≤≥]\s*(0\.\d+|\d+e-\d+)",
        text, re.I
    )
    stats["p_values"] = []
    for p in p_value_matches:
        try:
            val = float(p.replace('e', 'E'))
            if 0 < val < 1:
                stats["p_values"].append(val)
        except ValueError:
            pass
    
    # Extract effect sizes (Cohen's d, OR, RR, HR)
    effect_matches = re.findall(
        r"\b(?:d\s*=\s*|Cohen['']?s?\s*d\s*[=:]\s*|OR\s*[=:]\s*|RR\s*[=:]\s*|HR\s*[=:]\s*|"
        r"effect\s*size\s*[=:]\s*|beta\s*[=:]\s*)(-?\d+\.?\d*)",
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


def is_randomized_trial(text: str) -> bool:
    """Check if the study appears to be a randomized trial."""
    rct_patterns = [
        r"\brandomized\b",
        r"\brandomised\b",
        r"\brct\b",
        r"\brandomized controlled trial\b",
        r"\brandom assignment\b",
        r"\brandomly assigned\b",
        r"\brandom allocation\b"
    ]
    combined_pattern = "|".join(rct_patterns)
    return bool(re.search(combined_pattern, text, re.I))


def generate_headline(record: Dict) -> str:
    """Generate a plain-language headline from the study title."""
    title = record.get("title", "")
    
    # Remove common academic prefixes
    title = re.sub(r"^(A|An|The)\s+", "", title, flags=re.I)
    title = re.sub(r"^(Effect|Effects|Impact|Impacts|Efficacy|Association)\s+of\s+", "", title, flags=re.I)
    
    # Truncate if too long
    if len(title) > 100:
        title = title[:97] + "..."
    
    return title


def generate_summary(record: Dict, stats: Dict) -> str:
    """Generate a plain-language summary of the study."""
    title = record.get("title", "")
    abstract = record.get("abstract", "")
    
    # Get sample size
    sample_size = max(stats["participants"]) if stats["participants"] else None
    sample_desc = sample_size_descriptor(sample_size) if sample_size else "unknown"
    
    # Check if RCT
    full_text = f"{title} {abstract}"
    is_rct = is_randomized_trial(full_text)
    
    # Build summary
    if is_rct:
        if sample_size and sample_size >= 200:
            summary = f"This randomized controlled trial with {sample_size} participants "
        else:
            summary = "This randomized controlled trial "
    else:
        summary = "This study "
    
    # Try to extract the key finding from abstract
    # Look for "found", "showed", "demonstrated", "concluded"
    finding_match = re.search(
        r"(?:found|showed|demonstrated|concluded|results show|we found)\s+that\s+([^.]+\.)",
        abstract, re.I
    )
    if finding_match:
        summary += finding_match.group(1).lower()
    else:
        # Fallback to first sentence of conclusion if available
        conclusion_match = re.search(r"(?:conclusion|conclusions?)[:\s]+([^.]+\.)", abstract, re.I)
        if conclusion_match:
            summary += "found that " + conclusion_match.group(1).lower()
        else:
            summary += f"examined {title.lower()[:50]}."
    
    return summary


def process_medrxiv_record(record: Dict) -> Optional[Dict]:
    """
    Process a single medRxiv record and extract structured data.
    
    Args:
        record: Raw record from medRxiv API
        
    Returns:
        Processed record dict, or None if not suitable
    """
    title = record.get("title", "")
    abstract = record.get("abstract", "")
    full_text = f"{title} {abstract}"
    
    # Check if matches our topic criteria
    if not TOPIC_PATTERN.search(full_text):
        return None
    
    # Extract statistics
    stats = extract_statistics(full_text)
    
    # Get best p-value and effect size
    best_p = min(stats["p_values"]) if stats["p_values"] else None
    best_effect = None
    if stats["effect_sizes"]:
        # Use the largest absolute effect
        best_effect = max(stats["effect_sizes"], key=abs)
    
    # Get sample size
    sample_size = max(stats["participants"]) if stats["participants"] else None
    
    # Skip if no useful statistics
    if best_p is None and best_effect is None and sample_size is None:
        return None
    
    # Determine if this is an RCT
    is_rct = is_randomized_trial(full_text)
    
    # Calculate scores
    ultra_score = ultra_significance_score(best_p, best_effect, sample_size) if all([best_p, best_effect, sample_size]) else 0
    evidence_tier = determine_evidence_tier(best_p, best_effect, sample_size, is_rct)
    
    # Assign category
    category = assign_category(title, record.get("category", ""))
    
    # Generate headline and summary
    headline = generate_headline(record)
    summary = generate_summary(record, stats)
    
    study_id = f"medrxiv-{record.get('doi', '').replace('/', '-')}"

    return {
        "nct_id": study_id,
        "source": "medrxiv",
        "source_url": f"https://doi.org/{record.get('doi', '')}",
        "category": category,
        "evidence_tier": evidence_tier,
        "title": title,
        "headline": headline,
        "summary": summary,
        "intervention": "",  # Not easily extractable from abstract
        "intervention_description": "",
        "comparator": "",
        "population": "",
        "conditions": record.get("category", ""),
        "sample_size": sample_size or 0,
        "study_enrollment": sample_size or 0,
        "sample_size_category": sample_size_descriptor(sample_size) if sample_size else "",
        "num_arms": stats["arms"][0] if stats["arms"] else 2,
        "completion_date": record.get("date", ""),
        "outcome_name": "",
        "outcome_type": "",
        "control_mean": None,
        "control_sd": None,
        "control_n": None,
        "treatment_mean": None,
        "treatment_sd": None,
        "treatment_n": None,
        "ate": None,
        "effect_size": best_effect,
        "effect_magnitude": effect_magnitude(best_effect) if best_effect else "",
        "p_value": best_p,
        "ultra_score": ultra_score,
        "is_rct": is_rct,
    }


def fetch_and_process(start_date: str = None, end_date: str = None, max_results: int = 100) -> List[Dict]:
    """
    Fetch and process medRxiv preprints.
    
    Args:
        start_date: Start date (YYYY-MM-DD), defaults to 2020-01-01
        end_date: End date (YYYY-MM-DD), defaults to today
        max_results: Maximum number of processed results to return
        
    Returns:
        List of processed study records
    """
    if start_date is None:
        start_date = "2020-01-01"
    if end_date is None:
        end_date = dt.date.today().isoformat()
    
    print(f"Fetching medRxiv preprints from {start_date} to {end_date}...")
    print("Processing records...")
    processed = []
    cursor = 0
    fetched = 0

    while True:
        url = f"https://api.medrxiv.org/details/medrxiv/{start_date}/{end_date}/{cursor}/json"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            batch = response.json().get("collection", [])
        except requests.RequestException as e:
            print(f"Error fetching from medRxiv: {e}")
            break

        if not batch:
            break

        fetched += len(batch)
        print(f"  Fetched {fetched} records...")

        for record in batch:
            result = process_medrxiv_record(record)
            if result:
                processed.append(result)
                if len(processed) >= max_results:
                    break

        if len(processed) >= max_results:
            break

        cursor += 100
    
    # Sort by ultra_score descending
    processed.sort(key=lambda x: x.get("ultra_score", 0), reverse=True)
    
    print(f"Processed {len(processed)} relevant studies")
    return processed


def export_to_csv(results: List[Dict], output_path: str) -> int:
    """
    Export results to CSV format compatible with the frontend.
    
    Args:
        results: List of processed study records
        output_path: Path to output CSV file
        
    Returns:
        Number of rows exported
    """
    if not results:
        print("No results to export")
        return 0
    
    rows = [normalize_row(r) for r in results]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Exported {len(rows)} rows to {output_path}")
    return len(rows)


if __name__ == "__main__":
    # Run as standalone script
    results = fetch_and_process(max_results=50)
    
    # Print summary
    print("\n" + "="*60)
    print("MEDRXIV SCRAPER RESULTS")
    print("="*60)
    
    high_quality = [r for r in results if r["ultra_score"] > 0]
    print(f"Total processed: {len(results)}")
    print(f"High-quality (ultra_score > 0): {len(high_quality)}")
    
    if high_quality:
        print("\nTop findings:")
        for i, r in enumerate(high_quality[:5], 1):
            print(f"\n{i}. [{r['category'].upper()}] {r['headline'][:60]}")
            print(f"   Score: {r['ultra_score']:.2f}, p={r['p_value']}, effect={r['effect_size']}")
    
    # Export to CSV
    export_to_csv(results, "../frontend/data/medrxiv_trials.csv")
