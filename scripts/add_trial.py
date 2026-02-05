#!/usr/bin/env python3
"""Add a trial by searching ClinicalTrials.gov and staging the result.

Usage examples:
  python scripts/add_trial.py --search "walking outside cold wet head" --find-nct --dry-run
  python scripts/add_trial.py --input newtrial.json --find-nct

Writes candidates to data/staging/new_trials.csv (never modifies existing data/trials.csv).
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime

from pipeline.registry_lookup import search_clinicaltrials
from pipeline.validate_trial import title_similarity

STAGING_CSV = os.path.join("data", "staging", "new_trials.csv")
STAGING_HEADERS = [
    "nct_id", "title", "headline", "summary", "intervention", "conditions",
    "sample_size", "control_mean", "treatment_mean", "p_value", "evidence_url",
    "confidence", "date_staged"
]


def ensure_staging():
    os.makedirs(os.path.dirname(STAGING_CSV), exist_ok=True)
    if not os.path.exists(STAGING_CSV):
        with open(STAGING_CSV, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=STAGING_HEADERS)
            writer.writeheader()


def stage_row(row):
    ensure_staging()
    row_out = {k: row.get(k, "") for k in STAGING_HEADERS}
    row_out["date_staged"] = datetime.utcnow().isoformat()
    with open(STAGING_CSV, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=STAGING_HEADERS)
        writer.writerow(row_out)


def search_and_stage(query, max_results=5, auto_accept=0.85, dry_run=True, rps=1.0):
    print(f"Searching ClinicalTrials.gov for: {query}")
    candidates = search_clinicaltrials(query, max_results=max_results, rps=rps)

    if not candidates:
        print("No candidates found.")
        return

    # Rank by naive title similarity
    ranked = []
    for c in candidates:
        sim = title_similarity(query, c.get("brief_title") or c.get("official_title"))
        ranked.append((sim, c))

    ranked.sort(key=lambda x: x[0], reverse=True)

    for sim, c in ranked:
        print(f"Candidate: {c['nct_id']} (sim={sim:.2f}) — {c['brief_title']}")

    top_sim, top = ranked[0]
    if top_sim >= auto_accept:
        print(f"Auto-accepting top candidate {top['nct_id']} (sim={top_sim:.2f})")
        row = {
            "nct_id": top.get("nct_id") or "",
            "title": top.get("brief_title") or top.get("official_title") or "",
            "headline": top.get("brief_title") or "",
            "summary": "",
            "intervention": top.get("intervention") or "",
            "conditions": top.get("condition") or "",
            "sample_size": top.get("enrollment") or "",
            "control_mean": "",
            "treatment_mean": "",
            "p_value": "",
            "evidence_url": f"https://clinicaltrials.gov/study/{top.get('nct_id')}" if top.get("nct_id") else "",
            "confidence": f"{top_sim:.2f}"
        }
        if dry_run:
            print("Dry run: would stage the row:")
            print(json.dumps(row, indent=2))
        else:
            stage_row(row)
            print(f"Staged candidate to {STAGING_CSV}")
    else:
        print("Top candidate below auto-accept threshold; staging top 3 candidates for review")
        for sim, c in ranked[:3]:
            r = {
                "nct_id": c.get("nct_id") or "",
                "title": c.get("brief_title") or c.get("official_title") or "",
                "headline": c.get("brief_title") or "",
                "summary": "",
                "intervention": c.get("intervention") or "",
                "conditions": c.get("condition") or "",
                "sample_size": c.get("enrollment") or "",
                "control_mean": "",
                "treatment_mean": "",
                "p_value": "",
                "evidence_url": f"https://clinicaltrials.gov/study/{c.get('nct_id')}" if c.get("nct_id") else "",
                "confidence": f"{sim:.2f}"
            }
            if dry_run:
                print(json.dumps(r, indent=2))
            else:
                stage_row(r)
                print(f"Staged candidate {c.get('nct_id') or '<no-nct>'} (sim={sim:.2f})")


def main():
    parser = argparse.ArgumentParser(description="Add a trial by search and stage for review")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search", help="Free text search phrase to query ClinicalTrials.gov")
    group.add_argument("--input", help="JSON file with trial fields to stage directly")
    parser.add_argument("--find-nct", action="store_true", help="Attempt to find NCT via ClinicalTrials.gov")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Don't write to staging, just show")
    parser.add_argument("--auto-accept", type=float, default=0.85)
    parser.add_argument("--max", type=int, default=5)
    parser.add_argument("--rps", type=float, default=1.0)

    args = parser.parse_args()

    if args.search:
        if args.find_nct:
            search_and_stage(args.search, max_results=args.max, auto_accept=args.auto_accept, dry_run=args.dry_run, rps=args.rps)
        else:
            print("--find-nct not provided; to search ClinicalTrials.gov use --find-nct")
            sys.exit(1)

    if args.input:
        with open(args.input, encoding="utf-8") as fh:
            payload = json.load(fh)
        if args.dry_run:
            print(json.dumps(payload, indent=2))
        else:
            stage_row(payload)
            print(f"Staged row to {STAGING_CSV}")


if __name__ == "__main__":
    main()
