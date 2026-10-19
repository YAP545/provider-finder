"""Step 2: collect PUBLIC info from a provider's own site. Respects robots.txt, rate-limits,
fetches at most a handful of pages, never logs in, never touches social/marketplace sites."""
import copy
import json
import re
import time
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

import config

log = logging.getLogger(__name__)
CACHE = Path("data/cache")
_robots: dict = {}

LINK_GROUPS = {
    "about": ("about", "team", "who-we-are"),
    "services": ("service", "what-we-do", "solutions", "offer"),
    "portfolio": ("portfolio", "our-work", "case-stud", "projects", "work"),
    "pricing": ("pricing", "price", "rates", "packages"),
    "contact": ("contact", "get-in-touch", "hire"),
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BAD_EMAIL = re.compile(r"\.(png|jpe?g|gif|svg|webp|woff2?)$|sentry|example\.|wixpress|your(name|email)", re.I)

# Strict pricing detection: require real pricing phrases
PRICE_RE = re.compile(r"(?:[$€£₹]|USD|EUR|GBP|INR)\s?\d[\d,.]*\s?[kK]?(?:\s?(?:/|per)\s?(?:hr|hour|month|mo|project))?")
PRICE_CTX = re.compile(
    r"starting\s+(?:at|from|[$€£₹]|USD|EUR|GBP|INR)|starts?\s+(?:at|from)|"
    r"plans?\s+starts?\s+(?:at|from)|from\s+[$€£₹]|packages?\s+from|pricing\s+starts?|"
    r"/\s*hr\b|/\s*hour\b|per\s+hour|per\s+month|/\s*mo\b|/\s*month\b|per\s+project|"
    r"\brates?\b|\bcosts?\b|fixed\s+price",
    re.I,
)
PRICE_NOISE = re.compile(
    r"\bgrew\b|\bincreas(?:e|ed|ing)?\b|\brevenue\b|\bleads\b|\broi\b|\bsales\b|"
    r"in\s+a\s+year|case\s+stud(?:y|ies)|"
    r"budget\s+range|select\s+budget|what\'?s\s+your\s+budget|your\s+budget|"
    r"<\s*[$€£₹]|\d+k\s*-\s*\$?\d+k|"
    r"seed\s+fund|raised|secures?|funding|investment|series\s+[a-e]|venture\s+capital|\bmillion\b",
    re.I,
)
CONCISE_PATTERNS = [
    r"(?:starting(?:\s+(?:at|from))?|starts?\s+at|plans?\s+starts?\s+at|packages?\s+from|pricing\s+starts?(?:\s+at)?|from)\s+(?:(?:USD|EUR|GBP|INR|[$€£₹])\s?)?\d[\d,.]*\s?[kK]?(?:\s?(?:/|per)\s?(?:hr|hour|month|mo|project))?",
    r"(?:[$€£₹]|USD|EUR|GBP|INR)\s?\d[\d,.]*\s?[kK]?(?:\s?(?:/|per)\s?(?:hr|hour|month|mo|project))",
    r"(?:rates?|costs?)\s+(?:typically\s+fall\s+between\s+)?(?:[$€£₹]|USD|EUR|GBP|INR)\s?\d[\d,.]*(?:\s?(?:/|per)\s?(?:hr|hour|month|mo|project))?",
    r"(?:[$€£₹]|USD|EUR|GBP|INR)\s?\d[\d,.]*\s?[kK]?(?:\s*setup)?(?:\s*·\s*[$€£₹]\s?\d[\d,.]*(?:/|per)\s?(?:mo|month|hr|hour))?",
]
SOCIAL_HOSTS = ("linkedin.com", "twitter.com", "x.com", "github.com", "dribbble.com", "behance.net", "instagram.com")


# ---------- cache helper with TTL ----------
def is_cache_valid(cache_file: Path, ttl_days: int = None) -> bool:
    if ttl_days is None:
        ttl_days = getattr(config, "CACHE_TTL_DAYS", 14)
    if not cache_file.exists():
        return False
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        coll_at = data.get("collected_at")
        if not coll_at:
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            return datetime.now() - mtime < timedelta(days=ttl_days)
        dt = datetime.fromisoformat(coll_at)
        return datetime.now() - dt < timedelta(days=ttl_days)
    except Exception:
        return False


# ---------- polite fetching ----------
def _robots_for(base: str):
    if base in _robots:
        return _robots[base]
    rp = robotparser.RobotFileParser()
    try:
        r = requests.get(base + "/robots.txt", headers=config.HEADERS, timeout=config.TIMEOUT)
        if r.status_code in (401, 403):
            rp.disallow_all = True
        elif r.status_code >= 500:
            rp = None
        elif r.status_code >= 400:
            rp.parse([])          # no robots.txt -> allowed
        else:
            rp.parse(r.text.splitlines())
    except requests.RequestException:
        rp = None
    _robots[base] = rp
    return rp


def allowed(url: str) -> bool:
    p = urlparse(url)
    rp = _robots_for(f"{p.scheme}://{p.netloc}")
    return bool(rp and rp.can_fetch(config.BOT_NAME, url))


def fetch(url: str):
    if not allowed(url):
        log.info("robots.txt disallows or unreachable: %s", url)
        return None
    time.sleep(config.DELAY)
    try:
        r = requests.get(url, headers=config.HEADERS, timeout=config.TIMEOUT)
    except requests.RequestException:
        return None
    if r.status_code != 200 or "html" not in r.headers.get("content-type", "") or len(r.content) > 1_500_000:
        return None
    return BeautifulSoup(r.text, "html.parser")


# ---------- extraction helpers ----------
def page_text(soup) -> str:
    s = copy.copy(soup)
    for t in s(["script", "style", "noscript", "svg"]):
        t.decompose()
    return re.sub(r"\s+", " ", s.get_text(" ", strip=True))


def pick_links(soup, base_url: str) -> dict:
    host = urlparse(base_url).netloc.removeprefix("www.")
    found = {}
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#")[0]
        p = urlparse(href)
        if p.scheme not in ("http", "https") or p.netloc.removeprefix("www.") != host or p.path in ("", "/"):
            continue
        label = (a.get_text(" ", strip=True) + " " + p.path).lower()
        for group, keys in LINK_GROUPS.items():
            if group not in found and any(k in label for k in keys):
                found[group] = href
    return found


def extract_emails(soup, text: str, domain: str):
    emails = [a["href"][7:].split("?")[0] for a in soup.find_all("a", href=True) if a["href"].lower().startswith("mailto:")]
    emails += EMAIL_RE.findall(text)
    emails = [e.strip().lower() for e in emails if e and not BAD_EMAIL.search(e)]
    emails.sort(key=lambda e: not e.endswith(domain))   # prefer same-domain addresses
    return emails


def extract_phones(soup):
    return [a["href"][4:].strip() for a in soup.find_all("a", href=True) if a["href"].lower().startswith("tel:")]


REJECT_TERMS = [
    "grew", "increase", "revenue", "leads", "roi", "sales",
    "in a year", "case study", "budget range", "select budget", "your budget",
    "iphone", "ipad", "shop now", "samsung", "galaxy", "macbook", "pixel"
]
# We use re-based accept so "from" only matches as an offer phrase (near service context)
ACCEPT_TERMS_PLAIN = [
    "starting at", "starts at", "starting", "packages",
    "pricing", "per hour", "/hr", "per month", "/month", "per project", "rates", "cost"
]
# "from" is too generic on its own; only accept it when followed by currency
ACCEPT_FROM_RE = re.compile(r"from\s+[$€£₹]|from\s+(?:usd|eur|gbp|inr)\s*\d", re.I)
CURRENCY_RE = re.compile(r"[$€£₹]|USD\b|EUR\b|GBP\b|INR\b", re.I)


def extract_pricing(text: str):
    if not text:
        return []
    out = []
    # Find positions of currency symbols
    for m in CURRENCY_RE.finditer(text[:25000]):
        # Window of about 120 characters around currency symbol
        start = max(0, m.start() - 60)
        end = min(len(text), m.end() + 60)
        window = text[start:end]
        window_lower = window.lower()

        # Reject if contains any noise terms
        if any(term in window_lower for term in REJECT_TERMS):
            continue

        # Accept only if contains at least one offer term
        if not any(term in window_lower for term in ACCEPT_TERMS_PLAIN):
            if not ACCEPT_FROM_RE.search(window):
                continue

        # Make a short match (about 40 characters) around the currency match
        w_curr_pos = m.start() - start
        s_start = max(0, w_curr_pos - 15)
        s_end = min(len(window), w_curr_pos + 25)
        short_phrase = re.sub(r"\s+", " ", window[s_start:s_end]).strip()

        # Must have digits
        if not re.search(r"\d", short_phrase):
            continue

        norm = re.sub(r"\s+", "", short_phrase.lower())
        if not any(norm == re.sub(r"\s+", "", x.lower()) for x in out):
            out.append(short_phrase)
            if len(out) >= 3:
                break
    return out


def jsonld_country(soup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
            elif isinstance(x, dict):
                addr = x.get("address")
                if isinstance(addr, dict):
                    c = addr.get("addressCountry")
                    c = c.get("name") if isinstance(c, dict) else c
                    if isinstance(c, str) and c.strip():
                        return c.strip()
                stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
    return None


def guess_name(soup, domain: str) -> str:
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content"):
        return og["content"].strip()
    if soup.title and soup.title.string:
        return re.split(r"\s[|–—-]\s", soup.title.string.strip())[0][:80]
    return domain


# ---------- main ----------
def collect_one(cand: dict, refresh: bool = False):
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / f"{cand['domain']}.json"
    if not refresh and is_cache_valid(cache_file):
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    home = fetch(cand["url"])
    if home is None:
        return None
    links = pick_links(home, cand["url"])
    soups = {"home": home}
    for group, url in list(links.items())[: config.MAX_PAGES_PER_SITE - 1]:
        s = fetch(url)
        if s is not None:
            soups[group] = s

    domain = cand["domain"]
    texts, emails, phones, pricing, socials, portfolio = [], [], [], [], set(), []
    country = None
    for group, s in soups.items():
        t = page_text(s)
        texts.append(f"[{group}] {t[:2500]}")
        emails += extract_emails(s, t, domain)
        phones += extract_phones(s)
        pricing += extract_pricing(t)
        country = country or jsonld_country(s)
        for a in s.find_all("a", href=True):
            h = urljoin(cand["url"], a["href"])
            if any(x in urlparse(h).netloc for x in SOCIAL_HOSTS):
                socials.add(h.split("?")[0])
    if "portfolio" in links:
        portfolio.append(links["portfolio"])
    portfolio += [u for u in socials if "dribbble.com" in u or "behance.net" in u or "github.com" in u]

    country_source = "json-ld" if country else ""
    if not country:
        tld = domain.rsplit(".", 1)[-1]
        if tld in config.CCTLD_COUNTRY:
            country, country_source = config.CCTLD_COUNTRY[tld], "domain-tld (weak signal)"
    meta = home.find("meta", attrs={"name": "description"})

    pricing_list = list(dict.fromkeys(pricing))[:5]
    rec = {
        "name": guess_name(home, domain), "website": cand["url"], "domain": domain,
        "country": country or "Unknown", "country_source": country_source or "not found",
        "email": emails[0] if emails else "", "phone": phones[0] if phones else "",
        "social_links": sorted(socials)[:6], "pricing_snippets": pricing_list,
        "portfolio_urls": list(dict.fromkeys(portfolio))[:5],
        "meta_description": (meta.get("content", "").strip() if meta else "")[:300],
        "text_excerpt": "\n".join(texts)[:7000], "pages_checked": list(soups.keys()),
        "category_hint": cand["category_hint"], "source_query": cand["source_query"],
        "collected_at": date.today().isoformat(),
    }
    cache_file.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    return rec
