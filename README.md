**live @ [healthevidence.onrender.com](https://healthevidence.onrender.com/)**

# Health Evidence

Highlights health research you can trust, and calls out popular claims that aren't well supported by evidence.

## Repo layout

```
frontend/
  index.html, app.js, styles.css   # static site (no build step)
  data/
    clinical_trials.csv            # produced by the pipeline (one row per outcome × arm)
    weak_evidence.csv              # hand-authored
pipeline/
  clinical_trials.py               # fetches one hardcoded NCT and writes clinical_trials.csv
  requirements.txt
```

## Running locally

### Frontend

```bash
cd frontend
python -m http.server 8000
# http://localhost:8000
```

### Pipeline

```bash
cd pipeline
pip install -r requirements.txt
python clinical_trials.py
```

## How the data is built

### `clinical_trials.csv` 

### pipeline:

1. Pulls the study record from `clinicaltrials.gov/api/v2/studies/{nct_id}`.
2. Walks every PRIMARY outcome and every (control arm, treatment arm) pair.
3. Extracts mean / SD / n per arm; computes Cohen's d. If the API doesn't include a p-value, back-computes one via Welch's t-test using `scipy.stats.ttest_ind_from_stats`.
4. Assigns an evidence tier (see below).
5. Generates a templated headline and plain-language summary.
6. Writes one row per (outcome × treatment arm) — so a 4-arm dose-finding trial produces multiple rows.

### `weak_evidence.csv`

`study_id`, `claim`, `actual_finding`, `headline`, `summary`, `study_type`, `sample_size`, `category`, `why_weak`, `confounders`, `source_url`, `date_published`.

## Evidence tiers (current rules)

Implemented in [`evidence_tier()`](pipeline/clinical_trials.py#L48):

| Tier   | p-value     | Sample size | Effect size (\|d\|) |
| ------ | ----------- | ----------- | ------------------- |
| GOLD   | ≤ 0.001     | ≥ 100       | ≥ 0.5               |
| SILVER | ≤ 0.001 **and** n ≥ 1000 (any d), **or** p < 0.01 **and** \|d\| ≥ 0.3 **and** n ≥ 50 | | |
| BRONZE | anything else | | |

The frontend labels both GOLD and SILVER as "Strong Evidence" and shows the underlying tier as a badge color.

## Frontend behavior

- Loads `clinical_trials.csv` and `weak_evidence.csv` at startup with PapaParse.
- Aggregates pipeline rows by `nct_id`, so a single trial shows once with all its outcomes inside the modal.
- The "primary" outcome for the card view is picked by highest `ultra_score` (a heuristic combining p, |d|, and n — see [`ultra_significance_score()`](pipeline/clinical_trials.py#L44)).
- Tabs: Latest, Nutrition, Exercise, Health, Weak Evidence. Category is assigned in the pipeline by keyword-matching the intervention + condition strings.
- Verdict badges (Yes / Likely yes / Probably not / Uncertain) are derived from tier + headline keywords in [`determineVerdict()`](frontend/app.js#L34).

## Data sources

- **ClinicalTrials.gov** — for trial-level structured outcomes (pipeline)
- Weak-evidence claims are sourced manually, with PubMed links where applicable.
- integrate PubMed
- check https://www.the-scientist.com/tag/scientific-misconduct
- check https://realfood.gov/
- SPORTDiscus, Health Systems Evidence, HealthEvidence.org
- unconfoundednews.com