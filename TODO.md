### pipeline
- review all studies in @trials.csv and @weak_evidence.csv for factual correctness and linking to real studies in ClinicalTrials.gov; use the web and original data sources to corroborat information; fill in any missing data cells with the correct values and update any incorrect information. extract the correct NCT identifiers for studies pulled from clinicaltrials.gov (e.g. "nctId": "NCT03540771"). Currently the NCT identifiers are made-up in sequential order starting at NCT00000001 in trials.csv.
- [x] Implementation started: added `scripts/add_trial.py`, `scripts/fix_nct_ids.py`, `scripts/review_staged.py`, `pipeline/registry_lookup.py`, and `pipeline/validate_trial.py`. Staged outputs are in `data/staging/` and audits are written to `data/audit_log.csv`. No existing `data/*.csv` files were modified.
- **Resume notes:**
  - Install deps: `python3 -m pip install requests`.
  - To test a search (dry-run): `python scripts/add_trial.py --search "walking outside cold wet head" --find-nct --dry-run`.
  - To stage NCT candidates for placeholder IDs: `python scripts/fix_nct_ids.py --max 5` (writes `data/staging/nct_candidates.csv`).
  - To inspect and accept/reject staged items: `python scripts/review_staged.py --list --file nct` then `--accept INDEX` or `--reject INDEX` as needed.
- **Next steps (TODO):**
  - Add unit conversion & ATE enrichment into the staging pipeline (kg → lbs, cm → in, percent handling) so staged rows include units and ATE sentences.
  - Add an `--apply` / safe-merge path to create `data/trials.v2.csv` from approved staged rows and append audit metadata.
  - Add a short `scripts/README.md` and a demo JSON (e.g., the "wet head in cold" trial) for onboarding and testing.
  - Expand registry lookups (ICTRP/EudraCT/ISRCTN) and DOI/PubMed enrichment for trials not on ClinicalTrials.gov.
  - Implement stricter validation rules and unit tests for validation/lookup functions. ✅ Implementation started: added `scripts/add_trial.py`, `scripts/fix_nct_ids.py`, `scripts/review_staged.py`, and pipeline helpers in `pipeline/registry_lookup.py` and `pipeline/validate_trial.py`. All changes stage outputs to `data/staging/` and write audit entries to `data/audit_log.csv` — original CSVs are not overwritten. 

### frontend
- [x] show the ATE with units in plain english with correct units (e.g. "treated participants lost an average of 1.45lbs compared to the control goup") for studies with significant results. ✅ Implemented in `frontend/app.js` (shows ATE in list and modal when p < 0.001; units are standardized to American system where possible).
- [x] make the "RANDOMIZED TRIAL" label more prominent by using @rct_gold_medal.svg ✅ Implemented in `frontend/app.js` and `frontend/styles.css` (shows the gold medal SVG in method badges).

### long-term (ignore for now)
<!-- incorporate HealthEvidence.org, MedRxiv, ICTRP, PubMed -->
<!-- From HealthEvidence: "We search MEDLINE, Embase, CINAHL, and PsycINFO monthly and BIOSIS, Sociological Abstracts and SPORTDiscus annually. We conduct manual searches in the Cochrane Library, ACCESSSS, Health Systems Evidence and The Evidence for Policy & Practice Information Centre’s COVID-19 'living' systematic map of research. All databases have been searched from 1995 to present. Please contact us at info@healthevidence.org if you are interested in reviewing our detailed search strategy." -->
