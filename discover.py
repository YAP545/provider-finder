"""Step 1: find candidate provider websites with a free search API (DuckDuckGo via `ddgs`)."""
import re
import time
import logging
from urllib.parse import urlparse

from ddgs import DDGS

import config

log = logging.getLogger(__name__)


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _blocked(domain: str) -> bool:
    return any(domain == b or domain.endswith("." + b) for b in config.BLOCKED_DOMAINS)


def _query_plan():
    """Interleave categories so any early stop still gives a balanced mix."""
    plan = []
    depth = max(len(v) for v in config.CATEGORIES.values())
    for i in range(depth):
        for region in config.REGIONS:
            for cat, queries in config.CATEGORIES.items():
                if i < len(queries):
                    plan.append((cat, queries[i], region))
    return plan


def discover():
    """Yield unique candidates: {domain, url, category_hint, source_query, title}."""
    seen = set()
    for cat, query, region in _query_plan():
        try:
            results = DDGS().text(query, region=region, max_results=15)
        except Exception as e:  # rate limits etc.
            log.warning("search failed (%s / %s): %s", query, region, e)
            time.sleep(5)
            continue
        for r in results or []:
            url = r.get("href", "")
            domain = _domain(url)
            title = r.get("title", "")
            if not domain or domain in seen or _blocked(domain):
                continue
            if re.search(config.LISTICLE_RE, title, re.I):
                continue
            seen.add(domain)
            p = urlparse(url)
            yield {"domain": domain, "url": f"{p.scheme}://{p.netloc}", "category_hint": cat,
                   "source_query": f"{query} [{region}]", "title": title}
        time.sleep(2)
