#!/usr/bin/env python3
"""Basic reviewer tool for staged candidates written by add_trial.py and fix_nct_ids.py

Operations:
 - --list : print staged rows with index
 - --accept INDEX : accept a staged row and append to approved csv (data/staging/approved_trials.csv)
 - --reject INDEX : mark rejected (write to data/staging/rejected_trials.csv)

This is intentionally minimal; it creates an audit log entry for each action.
"""

import argparse
import csv
import os
from datetime import datetime

STAGED_NEW = os.path.join("data", "staging", "new_trials.csv")
STAGED_NCT = os.path.join("data", "staging", "nct_candidates.csv")
APPROVED = os.path.join("data", "staging", "approved_trials.csv")
REJECTED = os.path.join("data", "staging", "rejected_trials.csv")
AUDIT_LOG = os.path.join("data", "audit_log.csv")

AUDIT_HEADERS = ["timestamp", "action", "staged_file", "row_index", "note"]


def ensure_audit():
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    if not os.path.exists(AUDIT_LOG):
        with open(AUDIT_LOG, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=AUDIT_HEADERS)
            writer.writeheader()


def write_audit(action, staged_file, row_index, note=""):
    ensure_audit()
    with open(AUDIT_LOG, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=AUDIT_HEADERS)
        writer.writerow({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "staged_file": staged_file,
            "row_index": row_index,
            "note": note,
        })


def list_staged(file_path):
    if not os.path.exists(file_path):
        print(f"No staged file: {file_path}")
        return
    with open(file_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, 1):
            print(i, row)


def accept_row(file_path, row_index):
    # Read staged rows
    with open(file_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if row_index < 1 or row_index > len(rows):
        print("Index out of range")
        return
    row = rows[row_index - 1]

    # Append to approved file (preserve keys)
    os.makedirs(os.path.dirname(APPROVED), exist_ok=True)
    headers = list(row.keys())
    write_header = not os.path.exists(APPROVED)
    with open(APPROVED, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    write_audit("accept", file_path, row_index, note=f"Accepted row to {APPROVED}")
    print(f"Accepted staged row {row_index} to {APPROVED}")


def reject_row(file_path, row_index, reason=""):
    with open(file_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if row_index < 1 or row_index > len(rows):
        print("Index out of range")
        return
    row = rows[row_index - 1]

    # Append to rejected file
    headers = list(row.keys())
    write_header = not os.path.exists(REJECTED)
    with open(REJECTED, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    write_audit("reject", file_path, row_index, note=reason)
    print(f"Rejected staged row {row_index} (reason: {reason})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Review staged trial candidates")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", nargs="?", const="all", help="List staged rows (default: all)")
    group.add_argument("--accept", type=int, help="Accept a staged row by index from the specified staged file")
    group.add_argument("--reject", type=int, help="Reject a staged row by index")
    parser.add_argument("--file", choices=["new", "nct"], default="new", help="Which staged file to operate on")
    parser.add_argument("--reason", default="")

    args = parser.parse_args()

    file_map = {"new": STAGED_NEW, "nct": STAGED_NCT}
    file_path = file_map[args.file]

    if args.list is not None:
        list_staged(file_path)
    elif args.accept:
        accept_row(file_path, args.accept)
    elif args.reject:
        reject_row(file_path, args.reject, reason=args.reason)
