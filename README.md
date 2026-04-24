# CoE Dashboard

Automated data refresh for the CoE Portfolio executive dashboard.
Pulls live data from Asana, computes all metrics in business days, renders `output/index.html`.

## Install

```bash
cd CoEDashboard
pip install -r requirements.txt
```

Requires Python 3.9+.

## Configure

```bash
cp .env.example .env
```

Open `.env` and add your Asana Personal Access Token:
```
ASANA_PAT=your_token_here
```

Get a token at: https://app.asana.com/0/my-apps → Create new token.

## Run

```bash
# Pull fresh data from Asana → output/index.html
python run.py

# Use fixture data (no PAT needed, good for testing layout)
python run.py --dry-run

# Log every metric to stdout
python run.py --verbose
```

## Test

```bash
pytest tests/
```

## Deploy to Vercel (GitHub auto-deploy)

After every refresh, push to GitHub and Vercel redeploys automatically:

```bash
python run.py
git add output/index.html
git commit -m "refresh $(date +%Y-%m-%d)"
git push
```

Vercel settings: Root Directory = `output`

## Project structure

```
src/
  asana_client.py   # Fetches portfolio items from Asana API
  metrics.py        # All metric computations (pure functions, business days)
  renderer.py       # Jinja2 render + display value helpers
templates/
  dashboard.jinja   # HTML template with {{ placeholders }}
tests/
  test_metrics.py
  fixtures/
    sample_asana_response.json
output/
  index.html        # Generated file — committed for Vercel
run.py              # Entry point
```

## Key metrics

All durations are in **business days** (Mon–Fri, weekends excluded).

| Metric | Description |
|---|---|
| Review cycle | Received Date → First Review Date, substantive reviews only |
| Upstream lag | Created on → Received Date |
| Substantive | Tags not all in {Already Completed, No Needed, Not Needed, TBD} |
| Closed at gate | Tags all in {Already Completed, No Needed, Not Needed} |
| Delivered | completed=True AND classification≠Rejected AND status≠dropped |
