import csv
import math
import os
import requests
from typing import Dict, List, Optional

NCT_ID = "NCT04184622"
BASE_URL = "https://clinicaltrials.gov/api/v2"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "data", "clinical_trials.csv")

def safe_float(v):
    if v is None: return None
    try: return float(v)
    except (ValueError, TypeError): return None

def parse_pvalue(p):
    if p is None: return None
    if isinstance(p, (int, float)): return float(p)
    if isinstance(p, str):
        p = p.strip()
        if p.startswith('<'):
            v = safe_float(p[1:].strip())
            return (v * 0.5) if v is not None else None
        if p.startswith('>'): return safe_float(p[1:].strip())
        return safe_float(p)
    return None

def cohens_d(m1, m0, s1, s0, n1, n0):
    if None in (m1, m0, s1, s0, n1, n0) or n1 <= 1 or n0 <= 1: return None
    num = (n1 - 1) * s1**2 + (n0 - 1) * s0**2
    den = n1 + n0 - 2
    if den <= 0: return None
    pooled = math.sqrt(num / den)
    return (m1 - m0) / pooled if pooled > 0 else None

def effect_magnitude(d):
    if d is None: return None
    a = abs(d)
    if a >= 0.8: return 'large'
    if a >= 0.5: return 'medium'
    if a >= 0.2: return 'small'
    return 'negligible'

def ultra_significance_score(p, d, n):
    if p is None or p >= 0.001 or d is None or abs(d) < 0.5 or n is None or n < 20: return 0
    return -math.log10(max(p, 1e-20)) * abs(d) * math.log10(max(n, 10))

def evidence_tier(p, d, n):
    n = n or 0
    if p is not None and p <= 0.001 and n >= 100:
        if d is not None and abs(d) >= 0.5: return 'GOLD'
        if n >= 1000: return 'SILVER'
    if p is not None and d is not None:
        if p < 0.01 and abs(d) >= 0.3 and n >= 50: return 'SILVER'
    return 'BRONZE'

def sample_size_desc(n):
    if n is None or n < 50: return 'small'
    if n < 200: return 'moderate'
    if n < 1000: return 'large'
    return 'very large'

def assign_category(interv, cond):
    t = f"{interv or ''} {cond or ''}".lower()
    for k in ['diet', 'nutrition', 'supplement', 'vitamin', 'weight', 'fasting', 'egg', 'coffee']:
        if k in t: return 'nutrition'
    for k in ['exercise', 'physical activity', 'walking', 'training', 'fitness', 'yoga']:
        if k in t: return 'exercise'
    return 'health'

def is_mean_param(pt):
    if not pt: return True
    pt = str(pt).strip().lower()
    if "median" in pt: return False
    return "mean" in pt or "least_square" in pt

def is_baseline(lbl):
    if not lbl: return False
    return any(x in lbl.lower() for x in ["baseline", "pre-treatment", "screening"])

def dispersion_to_sd(m, n, outcome_dispersion_type=""):
    val = safe_float(m.get("spread")) or safe_float(m.get("dispersionValue"))
    typ = str(m.get("dispersionType") or outcome_dispersion_type or "").strip().lower()
    sd = None
    if val is not None:
        if typ in ("", "sd", "stdev") or "standard deviation" in typ: sd = val
        elif "standard error" in typ or typ in ("se", "sem"): sd = val * math.sqrt(n) if n else val
    if sd is None:
        u, l = safe_float(m.get("upperLimit")), safe_float(m.get("lowerLimit"))
        if u is not None and l is not None and u > l: sd = (u - l) / 4.0 if not n else (u - l) / (2 * 1.96) * math.sqrt(n)
    return sd

def pick_analysis(analyses, cid, tid):
    for a in analyses:
        gids = a.get("groupIds", [])
        if gids and len(gids) == 2 and cid in gids and tid in gids:
            return a
    for a in analyses:
        gids = a.get("groupIds", [])
        if gids and cid in gids and tid in gids:
            return a
    return None

def pick_measurement(sets, cid, tid, denoms):
    cand = [s for s in sets if cid in s["stats"] and tid in s["stats"]]
    if not cand: return None
    cand = [s for s in cand if not is_baseline(s.get('class_title', '') + s.get('category_title', ''))] or cand
    def sc(s):
        st = s["stats"]
        sd_ok = int(st[cid].get("sd") is not None) + int(st[tid].get("sd") is not None)
        tot = (denoms.get(cid) or 0) + (denoms.get(tid) or 0)
        return (sd_ok, tot)
    return max(cand, key=sc)

def fetch(nct_id: str) -> Optional[Dict]:
    try:
        r = requests.get(f"{BASE_URL}/studies/{nct_id}", timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return None

def metadata(d: Dict) -> Dict:
    p = d.get("protocolSection", {})
    idm, desc, design, arms, elig, status = p.get("identificationModule", {}), p.get("descriptionModule", {}), p.get("designModule", {}), p.get("armsInterventionsModule", {}), p.get("eligibilityModule", {}), p.get("statusModule", {})
    ints = arms.get("interventions", [])
    conds = p.get("conditionsModule", {}).get("conditions", [])
    enr = design.get("enrollmentInfo", {})
    comp = status.get("completionDateStruct", {})
    pop_parts = []
    mi, ma = elig.get("minimumAge"), elig.get("maximumAge")
    if mi and ma: pop_parts.append(f"ages {mi} to {ma}")
    elif mi: pop_parts.append(f"ages {mi} and older")
    elif ma: pop_parts.append(f"ages up to {ma}")
    if conds: pop_parts.append(f"with {', '.join(conds[:2])}")
    pop = ", ".join(pop_parts) if pop_parts else "adults"
    nct_id = idm.get("nctId", "")
    return {
        "study_id": nct_id,
        "source_url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else "",
        "title": idm.get("briefTitle", ""),
        "intervention_names": ", ".join(i.get("name", "") for i in ints),
        "intervention_description": "; ".join(i.get("description", "") for i in ints if i.get("description")),
        "conditions": ", ".join(conds),
        "population": pop,
        "enrollment": safe_float(enr.get("count")),
        "num_arms": len(arms.get("armGroups", [])),
        "date_published": comp.get("date", ""),
    }

def outcomes(d: Dict) -> List[Dict]:
    om = d.get("resultsSection", {}).get("outcomeMeasuresModule", {}).get("outcomeMeasures", [])
    out = []
    for o in om:
        if str(o.get("type") or "").upper() != "PRIMARY":
            continue
        groups_list = o.get("groups", [])
        gr = {g.get("id"): g.get("title", "") for g in groups_list if g.get("id")}
        cid = None
        for g in groups_list:
            tt = str(g.get("type") or "").lower()
            tl = str(g.get("title") or "").lower()
            if "control" in tt or "placebo" in tt or any(x in tl for x in ["control", "placebo", "usual care"]):
                cid = g.get("id"); break
        if not cid:
            for gid, tl in gr.items():
                if any(x in tl.lower() for x in ["control", "placebo", "usual care"]): cid = gid; break
        if not cid: continue
        tids = [gid for gid in gr if gid != cid]
        if not tids: continue
        denoms = {}
        for dm in o.get("denoms", []):
            for c in dm.get("counts", []):
                gid, val = c.get("groupId"), safe_float(c.get("value"))
                if gid is not None and val is not None: denoms[gid] = val
        disp_type = str(o.get("dispersionType") or "").strip()
        msets = []
        for cls in o.get("classes", []):
            for cat in cls.get("categories", []):
                st = {}
                for m in cat.get("measurements", []):
                    gid, mean = m.get("groupId"), safe_float(m.get("value"))
                    if gid is None or mean is None: continue
                    pt = m.get("paramType") or cat.get("paramType") or cls.get("paramType") or o.get("paramType")
                    pt_str = str(pt or "").strip().upper()
                    if not is_mean_param(pt) and pt_str != "NUMBER": continue
                    st[gid] = {"mean": mean, "sd": dispersion_to_sd(m, denoms.get(gid), disp_type)}
                if st: msets.append({"class_title": cls.get("title", ""), "category_title": cat.get("title", ""), "stats": st})
        if not msets: continue
        analyses = o.get("analyses", [])
        outcome_param_type = str(o.get("paramType") or "").strip()
        for tid in tids:
            ms = pick_measurement(msets, cid, tid, denoms)
            if not ms: continue
            st = ms["stats"]
            cs, ts = st[cid], st[tid]
            cn, tn = denoms.get(cid), denoms.get(tid)
            analysis = pick_analysis(analyses, cid, tid)
            p = parse_pvalue(analysis.get("pValue")) if analysis else None
            a_param_type = (analysis.get("paramType") or "").strip() if analysis else ""
            a_param_value = (analysis.get("paramValue") or "").strip() if analysis else ""
            ed = None
            if (cs.get("sd") and ts.get("sd") and cn and tn and cn > 1 and tn > 1):
                ed = cohens_d(ts["mean"], cs["mean"], ts["sd"], cs["sd"], tn, cn)
            if p is None and ed is not None:
                try:
                    from scipy.stats import ttest_ind_from_stats
                    _, p = ttest_ind_from_stats(ts["mean"], ts["sd"], tn, cs["mean"], cs["sd"], cn, equal_var=False)
                except Exception: pass
            tot = (cn or 0) + (tn or 0)
            out.append({
                "outcome_type": o.get("type", "").upper(),
                "outcome_name": o.get("title", ""),
                "outcome_param_type": outcome_param_type,
                "analysis_param_type": a_param_type,
                "analysis_param_value": a_param_value,
                "control_group": gr.get(cid, ""),
                "control_mean": cs["mean"], "control_sd": cs.get("sd"), "control_n": cn,
                "treatment_mean": ts["mean"], "treatment_sd": ts.get("sd"), "treatment_n": tn,
                "p_value": p, "effect_size": ed, "effect_magnitude": effect_magnitude(ed),
                "ultra_score": ultra_significance_score(p, ed, tot), "evidence_tier": evidence_tier(p, ed, tot),
            })
    return out

def headline(meta: Dict, o: Dict) -> str:
    iv = (meta.get("intervention_names") or "The intervention")[:60]
    on = (o.get("outcome_name") or "the outcome")[:50]
    tm, cm = o.get("treatment_mean"), o.get("control_mean")
    dr = "increased" if tm and cm and tm > cm else "reduced" if tm and cm else "affected"
    diff = f" by {abs(tm - cm):.1f}" if tm is not None and cm is not None and abs(tm - cm) > 0.1 else ""
    return f"{iv} {dr} {on.lower()}{diff}"

def summary(meta: Dict, o: Dict) -> str:
    cn, tn = o.get("control_n") or 0, o.get("treatment_n") or 0
    n = int(cn + tn)
    iv = (meta.get("intervention_names") or "the treatment")[:80]
    comp = (o.get("control_group") or "a control group").lower()
    if "placebo" in comp: comp = "a placebo"
    elif "control" in comp: comp = "a control group"
    pop = meta.get("population") or "participants"
    on = o.get("outcome_name") or "the outcome"
    s1 = f"Researchers randomly assigned {n} {pop} to receive either {iv} or {comp}."
    tm, cm = o.get("treatment_mean"), o.get("control_mean")
    s2 = f"Those receiving the treatment had {'higher' if tm and cm and tm > cm else 'lower'} {on.lower()} on average." if tm is not None and cm is not None else ""
    s3 = "This is strong evidence because participants were randomly assigned to groups."
    parts = [s1, s2, s3]
    a_type, a_val = o.get("analysis_param_type"), o.get("analysis_param_value")
    p = o.get("p_value")
    if a_type and a_val and p is not None:
        p_str = "p<0.001" if p < 0.001 else f"p={p:.3f}"
        parts.append(f"({a_type}: {a_val}, {p_str})")
    return " ".join(parts)

def run():
    data = fetch(NCT_ID)
    if not data:
        print("Failed to fetch trial"); return
    meta = metadata(data)
    outs = outcomes(data)
    if not outs:
        print("No outcomes parsed"); return
    cat = assign_category(meta.get("intervention_description", "") + " " + meta.get("intervention_names", ""), meta.get("conditions", ""))
    rows = []
    for o in outs:
        tot = (o.get("control_n") or 0) + (o.get("treatment_n") or 0)
        enr = meta.get("enrollment") or tot
        rows.append({
            "study_id": meta["study_id"], "source_url": meta["source_url"], "category": cat, "evidence_tier": o.get("evidence_tier", "BRONZE"),
            "title": meta["title"], "headline": headline(meta, o), "summary": summary(meta, o),
            "intervention": meta.get("intervention_names", ""), "intervention_description": meta.get("intervention_description", ""),
            "comparator": o.get("control_group", ""), "population": meta.get("population", ""), "conditions": meta.get("conditions", ""),
            "sample_size": tot, "study_enrollment": int(enr) if enr else tot, "sample_size_category": sample_size_desc(tot),
            "num_arms": meta.get("num_arms", 2), "date_published": meta.get("date_published", ""),
            "outcome_name": o.get("outcome_name", ""), "outcome_type": o.get("outcome_type", ""),
            "outcome_param_type": o.get("outcome_param_type", ""), "analysis_param_type": o.get("analysis_param_type", ""), "analysis_param_value": o.get("analysis_param_value", ""),
            "control_mean": o.get("control_mean"), "control_sd": o.get("control_sd"), "control_n": o.get("control_n"),
            "treatment_mean": o.get("treatment_mean"), "treatment_sd": o.get("treatment_sd"), "treatment_n": o.get("treatment_n"),
            "effect_size": o.get("effect_size"), "effect_magnitude": o.get("effect_magnitude", ""), "p_value": o.get("p_value"), "ultra_score": o.get("ultra_score", 0),
        })
    rows.sort(key=lambda r: r.get("ultra_score", 0), reverse=True)
    fieldnames = list(rows[0].keys())
    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")

if __name__ == "__main__":
    run()
