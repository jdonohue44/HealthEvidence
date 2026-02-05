**live @ [healthevidence.onrender.com](https://healthevidence.onrender.com/)**

# Health Evidence

This project highlights health research you can trust, and calls out popular claims that aren't well supported by evidence.

## What This Project Does

1. **Finds Strong Evidence**: Queries ClinicalTrials.gov for well-designed experiments with clear, reliable results.
2. **Distinguishes Strong from Weak**: Clearly labels "Strong Evidence" from proper experiments versus "Weak Evidence" from studies that only observed patterns.
3. **Explains It Simply**: Presents findings in plain language that anyone can understand, without scientific jargon.

## Project Structure

```
HealthEvidence/
├── pipeline/                    # Data collection and analysis
│   ├── results_analysis.py      # Fetch and analyze trials from ClinicalTrials.gov
│   ├── export_csv.py            # Export analyzed data to CSV
│   ├── scoring.py               # Effect size and significance scoring
│   ├── categories.py            # Category assignment (nutrition/exercise/health)
│   └── requirements.txt         # Python dependencies
├── frontend/                    # Static website
│   ├── index.html               # Main page
│   ├── styles.css               # Trust-first editorial styling
│   ├── app.js                   # Data loading and rendering
│   └── data/
│       ├── trials.csv           # Gold standard trial data
│       └── weak_evidence.csv    # Curated weak evidence claims
└── README.md
```

## Getting Started

### View the Frontend

The frontend is a static site with no build step required:

```bash
cd frontend
python -m http.server 8000
# Open http://localhost:8000 in your browser
```

### Run the Data Pipeline

1. Install Python dependencies:

```bash
cd pipeline
pip install -r requirements.txt
```

2. Run the analysis to fetch and score trials:

```bash
python results_analysis.py
```

3. Export to CSV for the frontend:

```bash
python export_csv.py
```

## Evidence Standards

### Strong Evidence

Studies labeled "Strong Evidence" meet ALL of these criteria:
- People were **randomly assigned** to groups (so we can trust the comparison)
- Results were **very unlikely to be a fluke** (p-value < 0.001)
- The effect was **meaningful, not tiny** (Cohen's d ≥ 0.5)
- **Enough people were tested** to be reliable (100+ participants)

Larger studies (500+ participants) are highlighted, as more people tested means more reliable results.

### Weak Evidence

Claims labeled "Weak Evidence" typically come from:
- Studies that **only observed patterns** without testing them
- Situations where **other explanations** weren't ruled out (e.g., wealth, lifestyle, healthcare access)
- Research with **industry funding** that may have influenced results

## Examples

### Strong Evidence Example

> **Eating more fiber lowers blood pressure**
> Researchers randomly assigned 1,240 adults with high blood pressure to either a high-fiber diet or their usual diet for 12 weeks. Those eating more fiber saw their blood pressure drop by about 8 points on average.
> This is strong evidence because participants were randomly assigned to groups, and the large sample size provides reliable estimates.

### Weak Evidence Example

> **Does tennis really add 10 years to your life?**
> You may have seen headlines saying tennis players live nearly a decade longer. This comes from a study that followed 8,577 people in Copenhagen over 25 years.
> Here's the problem: researchers didn't assign people to play tennis. They just watched who already played. The people who chose tennis were probably different in many ways—they may have had more money, better healthcare, or more friends.
> The study authors themselves wrote that we can't know if tennis actually caused the longer lifespan.

## Data Sources

- **ClinicalTrials.gov**: U.S. registry of clinical trials (primary source for strong evidence)
- **WHO ICTRP Trial Search**: International trial registry platform for global trials
- **PubMed**: Peer-reviewed literature for weak evidence curation and study context
- **arXiv**: Preprints for emerging evidence (treated as preliminary)
- **Data Colada**: Research commentary and methodological critiques
- **Blind Spots (book)**: Reference for common reasoning errors and blind spots in evidence

---

## Expanding the Dataset

The site currently has **50 strong evidence** studies and **25 weak evidence** claims. Here's how to add more.

### Adding More Strong Evidence (from ClinicalTrials.gov)

Strong evidence comes from the pipeline that queries ClinicalTrials.gov. To fetch more:

**1. Adjust the number of studies to analyze in `pipeline/export_csv.py`:**

```python
# In the __main__ block at the bottom of export_csv.py
run_export(max_studies=200)  # Increase this number
```

The pipeline analyzes many studies but only keeps those meeting strong evidence criteria (p < 0.001, effect size ≥ 0.5, sample size ≥ 100). You'll need to analyze roughly 4x the number of studies you want to end up with.

**2. Run the pipeline:**

```bash
cd pipeline
pip install -r requirements.txt
python export_csv.py
```

This will:
- Query ClinicalTrials.gov API for health/nutrition/exercise RCTs
- Calculate effect sizes and p-values
- Score and filter for strong evidence
- Export to `frontend/data/trials.csv`

**3. Review and edit the generated summaries** in `trials.csv` to ensure they're clear and accurate.

### Adding More Weak Evidence (Manual Curation)

Weak evidence must be manually researched and added. This is intentional—there's no reliable API for "popular but misleading health claims."

**To add a new entry, edit `frontend/data/weak_evidence.csv` with these fields:**

| Field | Description | Example |
|-------|-------------|---------|
| `study_id` | PubMed ID or DOI | `PMID:30193744` |
| `claim` | The viral/popular claim | `Tennis adds 9.7 years to your life` |
| `headline` | Simple question format | `Does tennis really add 10 years to your life?` |
| `summary` | Plain-language explanation (2-4 paragraphs) | See existing entries |
| `study_type` | Type of study | `Observational cohort` |
| `sample_size` | Number of participants | `8577` or `varies` |
| `category` | `nutrition`, `exercise`, or `health` | `exercise` |
| `why_weak` | Why the evidence is unreliable | Explain the methodological problems |
| `confounders` | Other possible explanations | `Income, healthcare access, lifestyle` |
| `source_url` | Link to original study | `https://pubmed.ncbi.nlm.nih.gov/...` |
| `date_published` | When published | `2018-09` |

**Good sources for finding weak evidence claims:**
- Health myth listicles and fact-checks
- Science journalism critiques
- Cochrane reviews that contradict popular beliefs
- Studies that went viral but have methodological problems

**Common patterns that make evidence weak:**
- Observational study reported as causal ("X linked to Y" becomes "X causes Y")
- Industry-funded research (cereal companies funding breakfast research)
- Animal studies applied to humans without evidence
- Marketing campaigns that became "common knowledge"
- Small sample sizes or cherry-picked outcomes

### Tips for Writing Clear Summaries

1. **Start with what people believe**: "You may have seen headlines saying..."
2. **Explain what the study actually showed**: "Here's what the study found..."
3. **Explain why it doesn't prove causation**: "But they didn't randomly assign people..."
4. **End with the takeaway**: "This type of study can spot patterns, but can't prove one thing caused another."

Avoid jargon. Write for someone who has never taken a science class.

---

## Technical Details

### Scoring Function

The ultra-significance score combines:

```
score = -log10(p_value) × |effect_size| × log10(sample_size)
```

Higher scores indicate more reliable, impactful findings.

### Sample Size Categories

| Participants | Category   |
|-------------|------------|
| < 50        | Small      |
| 50-199      | Moderate   |
| 200-999     | Large      |
| 1000+       | Very Large |

### Effect Size Interpretation (Cohen's d)

| d value | Interpretation |
|---------|----------------|
| 0.2     | Small effect   |
| 0.5     | Medium effect  |
| 0.8+    | Large effect   |
