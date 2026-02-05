"""Validation helpers for trial rows.

Functions:
 - title_similarity(a, b): fuzzy similarity score [0,1]
 - validate_trial(row): returns dict with checks and messages
"""

from difflib import SequenceMatcher
import math


def title_similarity(a, b):
    if not a or not b:
        return 0.0
    a_s = " ".join(str(a).lower().split())
    b_s = " ".join(str(b).lower().split())
    return SequenceMatcher(None, a_s, b_s).ratio()


def within_percent(a, b, pct=0.1):
    try:
        if a is None or b is None:
            return False
        a = float(a)
        b = float(b)
        if a == 0 and b == 0:
            return True
        diff = abs(a - b)
        return diff <= max(pct * max(abs(a), abs(b)), pct * 1, 1)
    except Exception:
        return False


def is_valid_p_value(p):
    try:
        p = float(p)
        return 0 < p <= 1
    except Exception:
        return False


def validate_trial(row):
    """Validate a trial-like dict (partial checks).

    Returns a dict with 'ok' (bool) and 'issues' (list of messages) and computed scores.
    """
    issues = []
    score = 0.0

    title = row.get("title") or row.get("headline")

    if title:
        score += 0.1
    else:
        issues.append("Missing title/headline")

    # Check sample size
    ss = row.get("sample_size")
    try:
        ss_n = int(ss) if ss is not None and ss != "" else None
        if ss_n and ss_n > 0:
            score += 0.2
        else:
            issues.append("Missing or invalid sample_size")
    except Exception:
        issues.append("sample_size not an integer")

    # Check p-value
    p = row.get("p_value")
    if p is not None and p != "":
        if is_valid_p_value(p):
            score += 0.2
        else:
            issues.append("Invalid p_value")
    else:
        issues.append("Missing p_value")

    # Means
    tmean = row.get("treatment_mean")
    cmean = row.get("control_mean")
    if tmean is not None and cmean is not None and tmean != "" and cmean != "":
        try:
            t = float(tmean)
            c = float(cmean)
            if not math.isfinite(t) or not math.isfinite(c):
                issues.append("Non-finite mean values")
            else:
                score += 0.1
        except Exception:
            issues.append("treatment_mean/control_mean not numeric")
    else:
        issues.append("Missing treatment or control means")

    # NCT format
    nct = row.get("nct_id")
    if nct:
        import re

        if re.match(r"^NCT\d{8}$", nct):
            score += 0.2
        else:
            issues.append(f"nct_id '{nct}' has unexpected format")
    else:
        issues.append("Missing nct_id")

    ok = len(issues) == 0
    return {"ok": ok, "issues": issues, "score": round(score, 2)}


if __name__ == "__main__":
    import argparse
    import csv

    parser = argparse.ArgumentParser(description="Validate trial rows from CSV (simple checks)")
    parser.add_argument("input", help="CSV file with trial rows")
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader, 1):
            res = validate_trial(row)
            print(f"{i}: ok={res['ok']} score={res['score']} issues={res['issues']}")
