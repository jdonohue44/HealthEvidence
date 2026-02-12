**live @ [healthevidence.onrender.com](https://healthevidence.onrender.com/)**

# Health Evidence

This project highlights health research you can trust, and calls out popular claims that aren't well supported by evidence.

## Getting Started

### View the Frontend

The frontend is a static site with no build step required:

```bash
cd frontend
python -m http.server 8000
# Open http://localhost:8000 in your browser
```

### Run the Data Pipeline

```bash
cd pipeline
pip install -r requirements.txt
python clinical_trials.py
```

Output: `frontend/data/clinical_trials.csv`

## Evidence Standards

### Strong Evidence

Studies labeled "Strong Evidence" meet ALL of these criteria:
- People were **randomly assigned** to groups (so we can trust the comparison)
- Results were **very unlikely to be a fluke** (p-value < 0.001)
- **Enough people were tested** to be reliable (1,000 participants)

### Weak Evidence

Claims labeled "Weak Evidence" typically come from:
- Studies that **only observed patterns** without testing interventions
- Situations where **other explanations (confounding factors)** weren't ruled out (e.g., wealth, lifestyle, healthcare access)

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

- **ClinicalTrials.gov**