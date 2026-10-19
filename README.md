# Provider Discovery & Research Tool

Finds freelancers/agencies (web dev, AI automation, design, marketing, business ops), collects **only publicly
published** details from their own websites, scores them with AI + transparent rules, shortlists the best, and
exports CSV/Excel with a Streamlit dashboard.

```
discover.py  ->  collect.py  ->  evaluate.py  ->  export.py  ->  app.py (Streamlit)
 (search)        (public pages)   (LLM + scoring)   (CSV/XLSX)     (dashboard)
```

## Quick start
```bash
pip install -r requirements.txt
cp .env.example .env          # set BOT_CONTACT and (optionally) a free LLM key
python pipeline.py --target 50           # ~15-30 min (polite 1.5s delay per request)
streamlit run app.py
```
Outputs: `data/providers.csv`, `data/providers.xlsx` (sheets: *All providers*, *Shortlist*).
Without an LLM key it runs in rule-based mode (`--no-ai`); the `ai_used` column shows which rows were AI-scored.

## Free tools used
| Need | Tool |
|---|---|
| Discovery | DuckDuckGo search via the `ddgs` package (no key) |
| Page parsing | requests + BeautifulSoup |
| AI evaluation | Any OpenAI-compatible endpoint: Gemini free tier, Groq free tier, or local Ollama |
| Dashboard | Streamlit (free hosting on Streamlit Community Cloud) |

## Data fields
name, website, country (+ how it was determined), services, key skills, portfolio links, pricing snippets,
public email/phone, social links, AI summary, experience evidence, red flags, sub-scores, suitability score,
shortlist flag, confidence, `ai_used`, source query, pages checked, collection date.

## Scoring (0-100)
`10 × (0.35·skill_relevance + 0.25·experience + 0.25·portfolio + 0.15·transparency)`
- **skill_relevance, experience** (0-10): judged by the LLM from page text only (keyword rules if no LLM).
- **portfolio** (0-10): computed in code from portfolio links and case-study mentions.
- **transparency** (0-10): computed in code: public email +4, phone +1, pricing +3, country +2.
Shortlist = top 10 with score ≥ 50 (edit in `config.py`). Weights are in `config.py` too.

## Ethics & "no invention" rules
- Only the provider's **own public website**; at most 5 pages each; 1.5s delay; descriptive User-Agent.
- Honors `robots.txt`; skips the site if it disallows us or can't be checked.
- Never touches LinkedIn, Upwork, Fiverr, Clutch, etc. (blocklist in `config.py`); social links are recorded, not scraped.
- Missing data stays empty / "Unknown" / "none found". Phones come only from `tel:` links; emails only if published.
- Country comes from structured data when present; otherwise a weak country-code-TLD hint (labelled as such); `.com` → Unknown.
- Page text is passed to the LLM as untrusted data, and the prompt forbids using outside knowledge.

## Known limitations (v1)
- Search results skew toward SEO-strong agencies; add queries/regions in `config.py`.
- JS-rendered sites may yield little text (low confidence, lower scores).
- Pricing detection is regex-based and may miss or mis-attribute figures; always verify before contacting.
- LLM scores are a screening aid, not a verdict. Review the evidence columns.

## Deploying the demo
Run the pipeline, commit `data/providers.csv`, push to GitHub, then deploy `app.py` on
[Streamlit Community Cloud](https://streamlit.io/cloud).

## Next steps
Async fetching, Playwright for JS sites (respecting robots), dedupe by company, user-weighted scoring, email-ready outreach drafts.
