"""Retrieve text from only the four approved India regulatory pages.

This module requests only the exact URLs listed below. It does not crawl pages,
follow hyperlinks found in page content, or download linked PDFs/documents.
"""

import re
from collections import Counter

import requests
from bs4 import BeautifulSoup

INDIA_SOURCES = [
    {
        "name": "SEBI — AML/CFT Guidelines for Securities Market Intermediaries",
        "url": "https://www.sebi.gov.in/legal/master-circulars/jun-2024/guidelines-on-anti-money-laundering-aml-standards-and-combating-the-financing-of-terrorism-cft-obligations-of-securities-market-intermediaries-under-the-prevention-of-money-laundering-act-2002-a-_83942.html",
    },
    {
        "name": "RBI — Master Direction: Know Your Customer (KYC), 2016",
        "url": "https://rbi.org.in/scripts/notificationuser.aspx?id=11566",
    },
    {
        "name": "RBI — Master Directions (ID 13641)",
        "url": "https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13641",
    },
    {
        "name": "RBI — Master Directions (ID 10738)",
        "url": "https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=10738",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

MAX_CHUNK_CHARS = 1200
MAX_CONTEXT_CHARS = 5500


def _clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _split_text(text, limit=MAX_CHUNK_CHARS):
    """Split long text into bounded chunks, preferring sentence/word boundaries."""
    text = _clean_text(text)
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind(". ", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut < 1:
            cut = limit
        else:
            cut += 1
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    return [chunk for chunk in chunks if chunk]


def _fetch_source(url: str):
    """Fetch and parse one exact approved page; never inspect/fetch href targets."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=(8, 30), allow_redirects=True)
        status = response.status_code
        content_type = response.headers.get("Content-Type", "unknown")
        body = response.text or ""
        soup = BeautifulSoup(body, "html.parser")
        title = _clean_text(soup.title.get_text(" ", strip=True)) if soup.title else "(no page title)"

        if status >= 400:
            return {"chunks": [], "error": f"HTTP {status}; content-type={content_type}; title={title}"}

        for element in soup.find_all(["script", "style", "noscript", "svg", "iframe", "nav", "footer"]):
            element.decompose()

        # Extract small semantic blocks, not parent <div>/<section> elements.
        # Parent containers often duplicate the entire page and create huge prompts.
        pieces = []
        seen = set()
        for element in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th"]):
            text = _clean_text(element.get_text(" ", strip=True))
            if len(text) >= 25 and text not in seen:
                seen.add(text)
                pieces.append(text)

        # Some pages have unusually flat markup. Fall back to body text, but split it.
        if not pieces:
            root = soup.body or soup
            visible_text = _clean_text(root.get_text(" ", strip=True))
            if len(visible_text) >= 250:
                pieces = _split_text(visible_text)

        all_text = " ".join(pieces)
        low_text = all_text.lower()
        challenge_markers = [
            "verify you are human", "access denied", "request blocked",
            "captcha", "checking your browser", "security challenge",
        ]
        if len(all_text) < 250 or any(marker in low_text for marker in challenge_markers):
            visible_preview = _clean_text((soup.body or soup).get_text(" ", strip=True))[:250]
            return {
                "chunks": [],
                "error": (
                    f"No substantive HTML text; HTTP {status}; content-type={content_type}; "
                    f"title={title}; response length={len(body)}; "
                    f"extracted text length={len(all_text)}; preview={visible_preview!r}"
                ),
            }

        chunks = []
        for piece in pieces:
            chunks.extend(_split_text(piece))
        return {"chunks": chunks, "error": None, "title": title}

    except requests.RequestException as exc:
        return {"chunks": [], "error": f"Network error: {type(exc).__name__}: {exc}"}
    except Exception as exc:
        return {"chunks": [], "error": f"Parsing error: {type(exc).__name__}: {exc}"}


def _terms(text: str):
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    stop = {
        "the", "and", "for", "with", "from", "that", "this", "what", "when",
        "where", "which", "who", "how", "does", "under", "are", "is", "to",
        "of", "in", "on", "a", "an", "or", "by", "be", "it", "as", "at",
        "can", "could", "should", "would", "please", "india", "rbi", "sebi",
    }
    return [word for word in words if len(word) > 2 and word not in stop]


def _fetch_all_sources():
    fetched_sources = []
    for source in INDIA_SOURCES:
        fetched = _fetch_source(source["url"])
        fetched_sources.append({**source, **fetched})
    return fetched_sources


def retrieve_india_context(question: str, max_chunks: int = 5):
    """Return a small, bounded context from the four approved pages only."""
    query_counts = Counter(_terms(question))
    ranked = []
    errors = []
    fetched_sources = _fetch_all_sources()

    for source in fetched_sources:
        if source.get("error"):
            errors.append(f"{source['name']}: {source['error']}")
            continue
        for chunk in source.get("chunks", []):
            chunk_counts = Counter(_terms(chunk))
            overlap = sum(min(count, chunk_counts.get(term, 0)) for term, count in query_counts.items())
            score = overlap / max(1, len(set(query_counts)))
            if score > 0:
                ranked.append((score, source, chunk))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[:max_chunks]

    # If no query terms match, still use a small sample from the approved pages
    # that were successfully retrieved; do not silently switch to other sources.
    if not selected:
        for source in fetched_sources:
            if source.get("error"):
                continue
            for chunk in source.get("chunks", [])[:2]:
                selected.append((0.0, source, chunk))
                if len(selected) >= max_chunks:
                    break
            if len(selected) >= max_chunks:
                break

    context_parts, source_urls = [], []
    used_chars = 0
    for _, source, chunk in selected:
        block = f"SOURCE: {source['name']}\nURL: {source['url']}\n{chunk}"
        remaining = MAX_CONTEXT_CHARS - used_chars
        if remaining <= 0:
            break
        if len(block) > remaining:
            block = block[:remaining]
        context_parts.append(block)
        used_chars += len(block) + 8
        if source["url"] not in source_urls:
            source_urls.append(source["url"])

    return {
        "context": "\n\n---\n\n".join(context_parts),
        "sources": source_urls,
        "errors": errors,
    }
