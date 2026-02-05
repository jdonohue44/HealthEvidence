#!/usr/bin/env python3
"""Find better NCT ids for rows that have placeholder or invalid NCT ids.

Writes candidates to data/staging/nct_candidates.csv for review. Does not modify existing data/trials.csv.
"""

import argparse
import csv
import os
import re
from pipeline.registry_lookup import search_clinicaltrials
from pipeline.validate_trial import title_similarity

TRIALS_CSV = os.path.join("data", "trials.csv")
STAGING_OUT = os.path.join("data", "staging", "nct_candidates.csv")
HEADERS = [
    "row_index", "current_nct", "title", "candidate_nct", "candidate_title",
    "candidate_enrollment", "candidate_completion_date", "similarity", "evidence_url"
]

PLACEHOLDER_RE = re.compile(r"^NCT0+1$|^NCT0{4,}|^NCT000000\d{1,3}$", re.IGNORECASE)
VALID_NCT_RE = re.compile(r"^NCT\d{8}$", re.IGNORECASE)


def ensure_staging():
    os.makedirs(os.path.dirname(STAGING_OUT), exist_ok=True)
    if not os.path.exists(STAGING_OUT):
        with open(STAGING_OUT, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=HEADERS)
            writer.writeheader()


def write_candidate(row_index, current_nct, title, cand, sim):
    ensure_staging()
    out = {
        "row_index": row_index,
        "current_nct": current_nct or "",
        "title": title or "",
        "candidate_nct": cand.get("nct_id") or "",
        "candidate_title": cand.get("brief_title") or cand.get("official_title") or "",
        "candidate_enrollment": cand.get("enrollment") or "",
        "candidate_completion_date": cand.get("completion_date") or "",
        "similarity": f"{sim:.2f}",
        "evidence_url": f"https://clinicaltrials.gov/study/{cand.get('nct_id')}" if cand.get("nct_id") else ""
    }
    with open(STAGING_OUT, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADERS)
        writer.writerow(out)


def is_placeholder(nct):
    if not nct:
        return True
    if VALID_NCT_RE.match(nct):
        return False
    if PLACEHOLDER_RE.search(nct):
        return True
    # treat anything not matching NCT12345678 as placeholder
    return True


def process(rps=1.0, max_candidates=5):
    if not os.path.exists(TRIALS_CSV):
        raise RuntimeError(f"{TRIALS_CSV} not found")

    ensure_staging()

    with open(TRIALS_CSV, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for idx, row in enumerate(reader, 1):
            nct = row.get("nct_id")
            title = row.get("title") or row.get("headline")

            if not is_placeholder(nct):
                continue

            # query the registry
            try:
                candidates = search_clinicaltrials(title or "", max_results=max_candidates, rps=rps)
            except Exception as exc:
                print(f"Lookup failed for row {idx}: {exc}")
                continue

            # rank by title similarity
            ranked = []
            for c in candidates:
                sim = title_similarity(title or "", c.get("brief_title") or c.get("official_title"))
                ranked.append((sim, c))
            ranked.sort(key=lambda x: x[0], reverse=True)

            if ranked:
                # write top candidate
                sim, cand = ranked[0]
                write_candidate(idx, nct, title, cand, sim)
                print(f"Row {idx}: staged candidate {cand.get('nct_id')} (sim={sim:.2f})")
            else:
                print(f"Row {idx}: no candidates found")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find and stage NCT id candidates for placeholder trials")
    parser.add_argument("--rps", type=float, default=1.0)
    parser.add_argument("--max", type=int, default=5)
    args = parser.parse_args()

    process(rps=args.rps, max_candidates=args.max)
