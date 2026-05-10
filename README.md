**live @ [healthevidence.onrender.com](https://healthevidence.onrender.com/)**

# Health Evidence

Highlighting health research you can trust based on evidence quality.

## Data sources

Studies are drawn from [PubMed](https://pubmed.ncbi.nlm.nih.gov/), a database of more than 40 million citations for biomedical literature from the National Library of Medicine. Individual records may link out to full text in medical journals. Data is sourced from PubMed and derivative medical journals. For educational purposes only. Not medical advice.

## Adding new trials

Curated studies live in **`frontend/data/clinical_trials.xlsx`**. To add a trial (or refresh an existing row):

1. **Identify the source.** Set **`study_id`** (for example `PMID:…` or `NCT…`) and **`source_url`** (PubMed, DOI, ClinicalTrials.gov, or another stable link).
2. **Add rows.** Use **one row per outcome or contrast** you want in the UI. Use the **same `study_id`** for multiple rows when one publication has several arms or outcomes worth listing separately.
3. **Set design and strength.** Fill **`study_type`** (`rct`, `observational`, `meta-analysis`, …) so badges match the design. Set **`evidence_tier`** to **GOLD**, **SILVER**, **BRONZE**, or **WEAK** using the rules below; use **WEAK** for observational work or for debunking overstated headlines.
4. **Write the card.** Complete **`category`** (`nutrition`, `exercise`, `medicine`, …), **`title`**, **`headline`**, **`summary`**, **`n`**, **`p_value`**, and **`difference`** so the list view and modal read clearly.

The app **merges rows by `study_id`**: one card per study, with each row as an outcome in the modal. The list card’s primary outcome is chosen by **tier** (higher first), then **`ultra_score`** if you populate it, then larger **`n`** (see Latest ordering).

These rules are a guide when assigning tiers in the workbook. **WEAK** is editorial (weak or misleading popular claims), not a statistical rule.

| Tier   | p-value     | Sample size | Effect size (\|d\|) |
| ------ | ----------- | ----------- | ------------------- |
| GOLD   | ≤ 0.001     | ≥ 100       | ≥ 0.5               |
| SILVER | ≤ 0.001 **and** n ≥ 1000 (any d), **or** p < 0.01 **and** \|d\| ≥ 0.3 **and** n ≥ 50 | | |
| BRONZE | anything else | | |

The frontend labels both GOLD and SILVER as **Strong Evidence** (badge color differs). **WEAK** shows a weak-evidence badge.

## Running locally

```bash
cd frontend
python -m http.server 8000
```

Open `http://localhost:8000`.