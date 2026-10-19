"""Automated unit tests for provider-finder without requiring internet or API keys."""
import pytest
from bs4 import BeautifulSoup
from unittest.mock import patch, MagicMock
from urllib.parse import urlparse

import collect
import evaluate
import config


# 1. Scraping tests: extracts email, phone, services, and pricing from sample HTML
def test_scraping_extraction():
    html = """
    <html>
        <head><title>Apex Software Studio | Web Development</title></head>
        <body>
            <h1>Custom Web Development and Automation</h1>
            <p>Contact us at <a href="mailto:hello@apexsoftware.com">hello@apexsoftware.com</a> or phone <a href="tel:+15551234567">Call Us</a>.</p>
            <div>
                Our packages starting at $2,500 per project provide complete full-stack web solutions.
            </div>
            <a href="/work">Our Portfolio</a>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    text = collect.page_text(soup)

    emails = collect.extract_emails(soup, text, "apexsoftware.com")
    assert "hello@apexsoftware.com" in emails

    phones = collect.extract_phones(soup)
    assert "+15551234567" in phones

    pricing = collect.extract_pricing(text)
    assert len(pricing) > 0
    assert any("2,500" in p for p in pricing)

    # Heuristic category & services extraction
    rec = {
        "text_excerpt": text,
        "category_hint": "Web Development",
        "meta_description": "Custom Web Development",
    }
    heur = evaluate.heuristic(rec)
    assert "Web development" in heur["services"]
    assert heur["primary_category"] == "Web Development"


# 2. Pricing tests: real prices are kept, funding/news snippets become "Unknown"
def test_pricing_filtering():
    # Real pricing text
    real_text = "We offer dedicated full-stack engineering packages starting at $75/hr for growing companies."
    prices = collect.extract_pricing(real_text)
    assert len(prices) == 1
    assert "$75/hr" in prices[0] or "75" in prices[0]

    # Funding / news noise snippet
    noise_text = "Cybersecurity startup raises $3 million in seed funding round from venture capital."
    noise_prices = collect.extract_pricing(noise_text)
    assert len(noise_prices) == 0

    # Case-study revenue text MUST return empty
    case_study_text = "Coalition grew a niche jeweler's revenue from $160k/mo to $315k/mo in a year"
    assert collect.extract_pricing(case_study_text) == [], \
        "Case-study revenue text should return empty"

    # Form budget dropdown MUST return empty
    form_text = "What's your budget range? < $5k $5k - $15k $15k - $50k"
    assert collect.extract_pricing(form_text) == [], \
        "Form budget dropdown should return empty"

    # 'Starting $990' MUST be accepted
    p990 = collect.extract_pricing("Starting $990")
    assert len(p990) > 0 and "990" in p990[0], \
        f"Starting $990 should be accepted, got {p990}"

    # '$50 per hour' MUST be accepted
    p50hr = collect.extract_pricing("$50 per hour")
    assert len(p50hr) > 0 and "50" in p50hr[0], \
        f"$50 per hour should be accepted, got {p50hr}"

    # 'Starting at ₹10,000' MUST be accepted
    p_rupee = collect.extract_pricing("Starting at ₹10,000")
    assert len(p_rupee) > 0 and "10,000" in p_rupee[0], \
        f"Starting at ₹10,000 should be accepted, got {p_rupee}"

    # Test evaluation output: empty pricing becomes "Unknown"
    rec_noise = {
        "name": "NoiseCo",
        "website": "https://noiseco.com",
        "domain": "noiseco.com",
        "country": "Unknown",
        "country_source": "not found",
        "email": "",
        "phone": "",
        "social_links": [],
        "pricing_snippets": noise_prices,
        "portfolio_urls": [],
        "meta_description": "Startup news",
        "text_excerpt": noise_text,
        "pages_checked": ["home"],
        "category_hint": "Other",
        "source_query": "query",
        "collected_at": "2026-10-19",
    }
    ev = evaluate.evaluate(rec_noise, use_ai=False)
    assert ev["pricing_info"] == "Unknown"
    assert ev["pricing_status"] == "Unknown"


# 3. Duplicate detection: www and trailing-slash variants collapse to higher-scored row
def test_duplicate_detection():
    rows = [
        {"name": "Alpha Lower", "website": "https://www.example.com/", "suitability_score": 45.0},
        {"name": "Alpha Higher", "website": "https://example.com", "suitability_score": 82.5},
        {"name": "Beta Other", "website": "https://beta.org/test/", "suitability_score": 60.0},
    ]
    deduped = evaluate.dedup_by_domain(rows)
    assert len(deduped) == 2
    domain_map = {urlparse(r["website"]).netloc.lower().removeprefix("www.").rstrip("/"): r for r in deduped}
    assert domain_map["example.com"]["suitability_score"] == 82.5
    assert domain_map["example.com"]["name"] == "Alpha Higher"


# 4. API failures: 429 and 503 trigger retries with backoff, and fallback is used
def test_api_failure_and_fallback():
    rec = {
        "name": "Test Agency",
        "website": "https://testagency.io",
        "domain": "testagency.io",
        "country": "United States",
        "country_source": "json-ld",
        "email": "contact@testagency.io",
        "phone": "555-9876",
        "social_links": [],
        "pricing_snippets": [],
        "portfolio_urls": ["https://testagency.io/case-studies"],
        "meta_description": "Top tier AI automation and development agency",
        "text_excerpt": "We are an AI automation agency specializing in workflow automation, chatbots, and n8n with 6 years experience.",
        "pages_checked": ["home"],
        "category_hint": "AI Automation",
        "source_query": "AI automation agency",
        "collected_at": "2026-10-19",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.ok = False
    mock_resp.text = "Too Many Requests"

    with patch("requests.post", return_value=mock_resp) as mock_post, patch("time.sleep", return_value=None):
        ev = evaluate.evaluate(rec, use_ai=True, refresh=True)

        assert mock_post.call_count == 5
        assert ev["ai_used"] is False
        assert ev["scored_by"] == "fallback"
        assert ev["category"] == "AI Automation"
        assert ev["suitability_score"] > 0


# 5. Scoring: sub-scores combine correctly and stay within 0-100
def test_scoring_calculation():
    rec = {
        "name": "Score Agency",
        "website": "https://scoreagency.com",
        "domain": "scoreagency.com",
        "country": "United Kingdom",
        "country_source": "domain-tld",
        "email": "info@scoreagency.com",
        "phone": "020-123456",
        "social_links": [],
        "pricing_snippets": ["starting at $50/hr"],
        "portfolio_urls": ["https://scoreagency.com/work", "https://dribbble.com/scoreagency"],
        "meta_description": "Web development agency",
        "text_excerpt": "Full-stack web development case study with 10 years experience serving corporate clients.",
        "pages_checked": ["home"],
        "category_hint": "Web Development",
        "source_query": "web development agency",
        "collected_at": "2026-10-19",
    }
    ev = evaluate.evaluate(rec, use_ai=False)
    score = ev["suitability_score"]
    assert 0.0 <= score <= 100.0

    heur = evaluate.heuristic(rec)
    skill = evaluate._clamp(heur.get("skill_relevance"))
    exp = evaluate._clamp(heur.get("experience_score"))
    portfolio = ev["portfolio_score"]
    transparency = ev["transparency_score"]

    w = config.WEIGHTS
    expected = round(10 * (
        w["skill"] * skill +
        w["experience"] * exp +
        w["portfolio"] * portfolio +
        w["transparency"] * transparency
    ), 1)
    assert score == expected


# 6. Verification rule: No strength claims public pricing when pricing_status is not Verified
def test_verified_only_claim_rule():
    import pandas as pd
    from pathlib import Path

    csv_path = Path("data/providers.csv")
    assert csv_path.exists()
    df = pd.read_csv(csv_path)

    for idx, row in df.iterrows():
        s = str(row.get("strengths", "")).lower()
        price_status = str(row.get("pricing_status", ""))
        if "public pricing" in s or "verified rates" in s:
            assert price_status == "Verified", f"Row {idx} ({row['name']}) claims public pricing/rates but status is {price_status}"
        if price_status != "Verified":
            assert "public pricing" not in s and "verified rates" not in s, f"Row {idx} ({row['name']}) has status {price_status} but strengths mentions pricing/rates"

