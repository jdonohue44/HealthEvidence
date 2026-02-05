# Data Source Assessment

This note summarizes the evaluation of additional data sources mentioned in `TODO.md`.

## PubMed

**Pros**
- Stable identifiers (PMID/PMCID) and reliable bibliographic metadata.
- Broad coverage of peer‑reviewed literature for weak evidence context.
- Free, well‑documented E‑utilities API for enrichment.

**Cons**
- No structured outcome data comparable to ClinicalTrials.gov results tables.
- RCT outcomes are not standardized, making automated effect size extraction unreliable.
- High risk of duplicate coverage with ClinicalTrials.gov for registered trials.

**Decision**
- **Do not** use PubMed as the primary source of strong‑evidence trials.
- **Do** use PubMed for weak‑evidence curation and metadata enrichment (IDs, dates, citation links).

## HealthEvidence.org

**Pros**
- Curated summaries of systematic reviews and evidence quality.
- Useful for high‑level synthesis beyond individual trials.

**Cons**
- No clear public API or bulk export workflow.
- Review‑level summaries would mix observational and interventional evidence with different rigor.

**Decision**
- Keep HealthEvidence.org separate from the trial‑level dataset.
- If integrated later, surface it as a **secondary synthesis layer** with distinct labeling to avoid
  conflating review summaries with individual RCTs.
