"""ClinicalTrials.gov lookup helpers

Provides a small, minimal wrapper around the ClinicalTrials.gov study_fields API for searching
by a free-text expression and returning ranked candidate studies.

This module is intentionally lightweight and has no heavy dependencies beyond `requests`.
"""

import time
import requests
from urllib.parse import quote_plus

API_BASE = "https://clinicaltrials.gov/api/query/study_fields"

DEFAULT_FIELDS = [
    "NCTId", "BriefTitle", "OfficialTitle", "EnrollmentCount", "CompletionDate",
    "Condition", "InterventionName", "StudyType", "Phrase"  # extra context
]


def search_clinicaltrials(expr, max_results=10, rps=1):
    """Search ClinicalTrials.gov using the study_fields API.

    Args:
        expr (str): search expression (title or combined fields). If it contains spaces it will
                    be quoted appropriately.
        max_results (int): maximum number of candidates to return (api supports paging).
        rps (float): requests-per-second rate limit.

    Returns:
        List[dict]: each dict contains fields: NCTId, BriefTitle, OfficialTitle, EnrollmentCount,
                    CompletionDate, Condition, InterventionName, match_score (placeholder)
    """
    # Sanitize expression for URL
    expr_q = quote_plus(expr)
    fields_q = ",".join(DEFAULT_FIELDS)

    # Limit the max we ask for (API allows up to 1000 in a single query but keep it small)
    max_results = max(1, min(int(max_results), 1000))
    url = f"{API_BASE}?expr={expr_q}&fields={fields_q}&min_rnk=1&max_rnk={max_results}&fmt=json"

    try:
        # Rate-limiting: simple sleep
        if rps and rps > 0:
            time.sleep(1.0 / float(rps))

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        studies = data.get("StudyFieldsResponse", {}).get("StudyFields", [])
        candidates = []
        for s in studies:
            candidate = {
                "nct_id": s.get("NCTId", [None])[0],
                "brief_title": s.get("BriefTitle", [None])[0],
                "official_title": s.get("OfficialTitle", [None])[0],
                "enrollment": next(iter(s.get("EnrollmentCount", [])), None),
                "completion_date": next(iter(s.get("CompletionDate", [])), None),
                "condition": next(iter(s.get("Condition", [])), None),
                "intervention": next(iter(s.get("InterventionName", [])), None),
                # raw study fields for debugging
                "raw": s,
            }
            candidates.append(candidate)

        return candidates

    except requests.RequestException as exc:
        raise RuntimeError(f"ClinicalTrials.gov API request failed: {exc}")


if __name__ == "__main__":
    # Quick manual test - will perform a live query when run
    import argparse

    parser = argparse.ArgumentParser(description="Search ClinicalTrials.gov")
    parser.add_argument("query", help="Search expression (title, intervention, etc)")
    parser.add_argument("--max", type=int, default=10)
    parser.add_argument("--rps", type=float, default=1.0)
    args = parser.parse_args()

    results = search_clinicaltrials(args.query, max_results=args.max, rps=args.rps)
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['nct_id']} — {r['brief_title']} (enrollment={r['enrollment']}, completion={r['completion_date']})")
