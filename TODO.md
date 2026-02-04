### pipeline
- extract the correct NCT identifiers for studies pulled from clinicaltrials.gov (e.g. "nctId": "NCT03540771"). Currently the NCT identifiers are made-up in sequential order starting at NCT00000001 in trials.csv
- improve the query to clinicaltrials.gov to get more popular health topics. I want to see things around "eating eggs", "red meat", "processed food", "saturated fats", "sweetener", "vaccination", and other popular controversial health topics. Most of the studies we have now are good, but I dont want the HPV one for example (too niche).
- incorporate MedRxiv (https://www.medrxiv.org/) "the preprint server for health sciences" studies as a source of research studies. See my sample script to get started @medrxiv_scraper.py
- incorporate International Clinical Trials Registry Platform (ICTRP) data using my bulk downloaded xml file @ICTRP-Results.xml
- use the book "Blind Spots: When Medicine Gets It Wrong, and What It Means for Our Health" by Marty Makary as a source of research studies, especially ones with weak evidence (e.g. peanut butter exposure, cholesterol from eggs, etc.)
- use the blog "Data Colada - Thinking about evidence and vice versa" by Uri Simonsohn, Leif Nelson and Joe Simmons as a source of research studies, especially for debunked research (e.g. "Harvard’s Gino Report Reveals How A Dataset Was Altered", "Evidence of Fraud in an Influential Field Experiment About Dishonesty", etc.)

### frontend
- make the titles stand out more. Try using simple questions as a way to do this, e.g. "Does eating processed meat increase your risk of cancer?" 
- make it crystal clear between the headline and the evidence label if this information is reliably true or not. E.g., for the title: "Can you target fat loss to specific areas?" having "weak evidence" there should be a bold "probably not" answer. Same for "Does stretching before exercise prevent injuries?". 
- include the p-value and average treatment effect in the cards at the bottom, in addition to the # of people tested.


