# Provider Finder

A research tool that automatically discovers, evaluates, and ranks service providers (web development, AI automation, design, marketing, and business operations agencies/freelancers) by crawling their own websites — no marketplace or directory data used.

**Live demo → [provider-finder-5epi8nt2sk64a3kwetgvnr.streamlit.app](https://provider-finder-5epi8nt2sk64a3kwetgvnr.streamlit.app/)**

---

## What it does

- **Discovery** — searches DuckDuckGo across five categories and six regions (US, UK, India, Australia, Canada, global) using `ddgs`; filters out marketplaces, directories, and listicle pages
- **Collection** — visits each provider's own website (home + up to 4 sub-pages: about, services, portfolio, pricing, contact); respects `robots.txt` and rate-limits
- **Extraction** — pulls services, key skills, email, phone, social links, portfolio URLs, pricing snippets, and country from page text and JSON-LD structured data
- **LLM evaluation & caching** — sends page text to Google Gemini (or any OpenAI-compatible endpoint) to classify the provider, extract skills, assess experience, and summarize; caches every LLM result on disk (`data/cache/llm/<domain>.json`) so rerun calls only evaluate new providers
- **Resilient API calling** — exponential backoff with jitter (up to 5 retries starting at 2s) for HTTP 429 and 503 errors, logging status codes on failures
- **Transparent scoring** — suitability score (0–100) is computed in code from four weighted sub-scores: **skill relevance** (35%), **experience** (25%), **portfolio** (25%), and **transparency** (15%); the LLM never picks the final score directly
- **Domain deduplication** — normalizes provider domains (stripping `www.` and trailing slashes) and keeps only the highest-scoring row
- **Selective rescoring** — `--rescore-fallback` allows re-scoring only rows where the AI was previously not used, reusing cached website data without touching other rows
- **Shortlisting & export** — top 10 providers with score ≥ 50 flagged as shortlisted; exported to `data/providers.csv` and formatted `data/providers.xlsx`
- **Dashboard** — interactive Streamlit app with filters, AI vs. fallback badges, score breakdown progress bars, side-by-side provider comparison (2–3 providers), and CSV/Excel downloads

---

## How scoring works

The final **suitability score** is:

```
score = 10 × (0.35 × skill + 0.25 × experience + 0.25 × portfolio + 0.15 × transparency)
```

| Sub-score | Source | Max |
|-----------|--------|-----|
| **skill** (0–10) | LLM's `skill_relevance` field — how clearly the site shows expertise in its category | 10 |
| **experience** (0–10) | LLM's `experience_score` — years mentioned, named clients, case studies | 10 |
| **portfolio** (0–10) | Code-counted: 2+ portfolio URLs → 8 pts, 1 → 5 pts; +2 if "case study" appears in text | 10 |
| **transparency** (0–10) | Code-counted: email (+4), phone (+1), public pricing (+3), known country (+2) | 10 |

**Keyword-rule fallback** (used when no LLM key is set or the API call fails): skill relevance is estimated from regex hit counts across eight service patterns; experience score is derived from year mentions and "clients"/"case study" keywords. The fallback is recorded in `scored_by` ("AI" or "fallback") and reflected with clear badges in the dashboard.

---

## Project structure

```
provider-finder/
├── pipeline.py          # Entry point: orchestrates discovery, collection, evaluation, export
├── discover.py          # Step 1 — DuckDuckGo search, candidate filtering
├── collect.py           # Step 2 — website crawl, extraction (email/phone/pricing/portfolio)
├── evaluate.py          # Step 3 — LLM evaluation + disk caching + backoff + keyword fallback + scoring
├── export.py            # Step 4 — CSV + formatted Excel output
├── config.py            # All settings: categories, weights, blocked domains, LLM config
├── app.py               # Streamlit dashboard (filters, comparison, progress bars, CSV/Excel downloads)
├── requirements.txt     # Python dependencies
├── .env.example         # Template — copy to .env and fill in your values
└── data/
    ├── providers.csv    # Pipeline output (tracked in git as example data)
    ├── providers.xlsx   # Same data, formatted Excel
    └── cache/           # Cached website data and LLM responses (git-ignored)
        └── llm/         # Per-domain LLM responses JSON cache
```

---

## Run locally

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env   # Windows: copy .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_API_KEY` | Yes (for AI mode) | Your Google Gemini API key (or key for any OpenAI-compatible endpoint) |
| `LLM_MODEL` | Yes (for AI mode) | Model name, e.g. `gemini-2.5-flash` |
| `LLM_BASE_URL` | No | Leave blank for Gemini; set to your endpoint URL for Groq, Ollama, etc. |
| `BOT_CONTACT` | No | Your contact email added to the crawler's User-Agent string |

> Without `LLM_API_KEY` / `LLM_MODEL` the pipeline still runs in keyword-rule mode — no API key needed.

### 3. Run the pipeline

```bash
python pipeline.py --target 50          # collect and evaluate 50 providers (AI mode with caching)
python pipeline.py --target 50 --no-ai  # keyword-rules only, no API calls
python pipeline.py --rescore-fallback   # re-scores only previous fallback rows using AI & cached site data
```

Results are saved to `data/providers.csv` and `data/providers.xlsx`.

### 4. Launch the dashboard

```bash
python -m streamlit run app.py
```

---

## Tech

- **Python 3.10+**
- **Streamlit** — interactive dashboard
- **pandas** — data wrangling and CSV/Excel I/O
- **openpyxl** — formatted Excel export
- **requests + BeautifulSoup4** — polite website crawling
- **ddgs** — DuckDuckGo search API (no key required)
- **Google Gemini API** (optional) — LLM evaluation via `google-generativeai`-compatible REST endpoint
- **python-dotenv** — environment variable loading

---

## Limitations

- **Rate limits** — DuckDuckGo and the Gemini free tier both throttle heavy usage; exponential backoff with jitter handles temporary 429/503 spikes, but very large runs may need pacing
- **Pricing extraction is heuristic** — only real pricing phrases (e.g. "starting at $X", "/hr", "per month", "packages from") are captured; results vary by how clearly a provider publishes rates
- **Search availability** — discovery depends on DuckDuckGo returning results for the configured queries; niche categories or regions may yield fewer candidates
- **robots.txt compliance** — sites that disallow crawling are skipped entirely, which can reduce coverage
- **Country detection** — derived from JSON-LD structured data or ccTLD; many providers will show as "Unknown"
- **No login or JavaScript rendering** — dynamic/SPA sites that require JS to display content will return limited text
