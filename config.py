"""Central settings. Edit CATEGORIES / BLOCKED_DOMAINS to steer discovery."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_NAME = "ProviderResearchBot"
BOT_CONTACT = os.getenv("BOT_CONTACT", "not-set")
HEADERS = {"User-Agent": f"{BOT_NAME}/0.1 (research prototype; contact: {BOT_CONTACT})"}
TIMEOUT = 10
DELAY = 1.5            # seconds between requests (be polite)
MAX_PAGES_PER_SITE = 5
CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "14"))

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

SHORTLIST_SIZE = 10
SHORTLIST_MIN_SCORE = 50
WEIGHTS = {"skill": 0.35, "experience": 0.25, "portfolio": 0.25, "transparency": 0.15}

CATEGORIES = {
    "Web Development": ["web development agency", "freelance web developer", "custom website development company"],
    "AI Automation": ["AI automation agency", "freelance AI automation consultant", "workflow automation agency"],
    "Design": ["UI UX design studio", "freelance brand designer", "web design agency"],
    "Marketing": ["digital marketing agency", "freelance SEO consultant", "content marketing agency"],
    "Business Operations": ["virtual assistant agency", "small business operations consultant", "outsourced bookkeeping firm"],
}
REGIONS = ["us-en", "uk-en", "in-en", "au-en", "ca-en", "wt-wt"]

# Marketplaces, social networks and directories: restrictive ToS and/or not the provider's own site.
BLOCKED_DOMAINS = {
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "reddit.com",
    "upwork.com", "fiverr.com", "freelancer.com", "toptal.com", "peopleperhour.com", "guru.com",
    "clutch.co", "goodfirms.co", "designrush.com", "sortlist.com", "g2.com", "trustpilot.com", "yelp.com",
    "medium.com", "quora.com", "pinterest.com", "wikipedia.org", "indeed.com", "glassdoor.com",
    "crunchbase.com", "behance.net", "dribbble.com", "github.com", "forbes.com", "techradar.com",
    "zapier.com", "hubspot.com", "wordpress.org", "wix.com", "shopify.com", "google.com", "bing.com",
    "itprofiles.com", "selectedfirms.co", "aicompanydirectory.com", "grokipedia.com",
}
LISTICLE_RE = r"\b(top|best)\s+\d+|\blist of\b|\bvs\.?\b|\bhow to\b|\bguide\b"

CCTLD_COUNTRY = {
    "uk": "United Kingdom", "in": "India", "au": "Australia", "ca": "Canada", "de": "Germany", "fr": "France",
    "nl": "Netherlands", "es": "Spain", "it": "Italy", "pl": "Poland", "pk": "Pakistan", "bd": "Bangladesh",
    "ae": "United Arab Emirates", "sg": "Singapore", "nz": "New Zealand", "ie": "Ireland", "za": "South Africa",
    "br": "Brazil", "se": "Sweden", "dk": "Denmark", "pt": "Portugal", "ng": "Nigeria", "ph": "Philippines",
}
