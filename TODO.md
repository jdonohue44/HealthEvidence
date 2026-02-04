### pipeline
- extract the correct NCT identifiers for studies pulled from clinicaltrials.gov (e.g. "nctId": "NCT03540771"). Currently the NCT identifiers are made-up in sequential order starting at NCT00000001 in trials.csv
- thoroughly review all studies in @trials.csv and weak_evidence.csv for correctness and robustness; use the web and original data sources to corroborate; fill in any missing data cells with the correct values

- incorporate MedRxiv (https://www.medrxiv.org/) "the preprint server for health sciences" studies as a source of research studies. See my sample script to get started @medrxiv_scraper.py
- incorporate International Clinical Trials Registry Platform (ICTRP) data using my bulk downloaded xml file @ICTRP-Results.xml
- incorporate PubMed studies

### frontend
- show the ATE when available

