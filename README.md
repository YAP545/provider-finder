# Provider Finder

A research tool that automatically discovers, evaluates, and ranks service providers (web development, AI automation, design, marketing, and business operations agencies/freelancers) by crawling their own websites — no marketplace or directory data used.

**Live demo → [provider-finder-5epi8nt2sk64a3kwetgvnr.streamlit.app](https://provider-finder-5epi8nt2sk64a3kwetgvnr.streamlit.app/)**

---

## What it does

- **Discovery** — searches DuckDuckGo across five categories and six regions (US, UK, India, Australia, Canada, global) using `ddgs`; filters out marketplaces, directories, and listicle pages
- **Collection** — visits each provider's own website (home + up to 4 sub-pages: about, services, portfolio, pricing, contact); respects `robots.txt` and rate-limits
- **Extraction** — pulls services, key skills, email, phone, social links, portfolio URLs, pricing snippets, and country from page text and JSON-LD structured data
- **LLM evaluation** — sends page text to Google Gemini (or any OpenAI-compatible endpoint) to classify the provider, identify services/skills, assess experience evidence, and generate a summary; falls back to keyword-rule heuristics if the API call fails or no key is configured
- **Transparent scoring** — suitability score (0–100) is computed in code from four weighted sub-scores: **skill relevance**, **experience**, **portfolio**, and **transparency**; the LLM never picks the score directly
- **Shortlisting** — top 10 providers with score ≥ 50 are flagged as shortlisted
- **Dashboard** — Streamlit app with sidebar filters (category, country, min score, shortlisted only, has pricing, keyword search) plus per-provider detail view and CSV download
- **Export** — results saved to `data/providers.csv` and `data/providers.xlsx` (two sheets: All providers + Shortlist, formatted with frozen header row)

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

**Keyword-rule fallback** (used when no LLM key is set or the API call fails): skill relevance is estimated from regex hit counts across eight service patterns (web dev, AI/automation, UI/UX, branding, SEO, content marketing, virtual assistance, bookkeeping); experience score is derived from year mentions and "clients"/"case study" keywords. The fallback is always noted in the `confidence` and `ai_used` columns.

---

## Project structure

```
provider-finder/
├── pipeline.py          # Entry point: orchestrates all four steps
├── discover.py          # Step 1 — DuckDuckGo search, candidate filtering
├── collect.py           # Step 2 — website crawl, extraction (email/phone/pricing/portfolio)
├── evaluate.py          # Step 3 — LLM evaluation + keyword fallback + scoring
├── export.py            # Step 4 — CSV + formatted Excel output
├── config.py            # All settings: categories, weights, blocked domains, LLM config
├── app.py               # Streamlit dashboard
├── requirements.txt     # Python dependencies
├── .env.example         # Template — copy to .env and fill in your values
└── data/
    ├── providers.csv    # Pipeline output (tracked in git as example data)
    ├── providers.xlsx   # Same data, formatted Excel
    └── cache/           # Per-domain JSON cache (git-ignored)
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
python pipeline.py --target 50        # collect and evaluate 50 providers (AI mode)
python pipeline.py --target 50 --no-ai  # keyword-rules only, no API calls
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

- **Rate limits** — DuckDuckGo and the Gemini free tier both throttle heavy usage; the pipeline adds delays and retries but very large runs may hit 429s
- **Pricing extraction is heuristic** — only real pricing phrases (e.g. "starting at $X", "/hr", "per month", "packages from") are captured; results vary by how clearly a provider publishes rates
- **Search availability** — discovery depends on DuckDuckGo returning results for the configured queries; niche categories or regions may yield fewer candidates
- **robots.txt compliance** — sites that disallow crawling are skipped entirely, which can reduce coverage
- **Country detection** — derived from JSON-LD structured data or ccTLD; many providers will show as "Unknown"
- **No login or JavaScript rendering** — dynamic/SPA sites that require JS to display content will return limited text
