"""Retrieve text from only the four approved India regulatory pages.

This module requests only the exact URLs listed below. It does not crawl pages,
follow hyperlinks found in page content, or download linked PDFs/documents.
"""

import re
from collections import Counter

import requests
import streamlit as st
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

# Use a normal browser-style request header rather than identifying the request
# as a custom research bot. This does not bypass authentication or access controls.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "keep-alive",
}


def _clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def _fetch_source(url: str):
    """Fetch and parse one exact approved page; never inspect/fetch href targets."""
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=(8, 30),
            allow_redirects=True,
        )
        status = response.status_code
        content_type = response.headers.get("Content-Type", "unknown")
        body = response.text or ""
        soup = BeautifulSoup(body, "html.parser")
        title = _clean_text(soup.title.get_text(" ", strip=True)) if soup.title else "(no page title)"

        if status >= 400:
            return {
                "chunks": [],
                "error": f"HTTP {status}; content-type={content_type}; title={title}; final URL={response.url}",
            }

        # Remove non-content elements. This only removes nodes from the downloaded
        # HTML; it does not follow links or make any additional requests.
        for element in soup.find_all(
            ["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg"]
        ):
            element.decompose()

        root = soup.find("main") or soup.find("article") or soup.body or soup
        pieces = []
        seen = set()
        for element in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "div"]):
            text = _clean_text(element.get_text(" ", strip=True))
            # Skip tiny UI labels and repeated nested div text. Keep reasonably
            # long blocks, including content that RBI puts inside table/div tags.
            if len(text) >= 45 and text not in seen:
                seen.add(text)
                pieces.append(text)

        # A broad body-text fallback is useful for sites with unusual markup.
        # Do not mistake a short title/navigation shell for regulatory content.
        if not pieces:
            fallback = _clean_text(root.get_text(" ", strip=True))
            if len(fallback) >= 250:
                pieces = [fallback]

        # Detect likely challenge pages rather than returning their text as law.
        combined = " ".join(pieces).lower()
        challenge_markers = [
            "verify you are human", "access denied", "request blocked",
            "captcha", "checking your browser", "security challenge",
        ]
        if any(marker in combined for marker in challenge_markers) or (
            len(combined) < 250 and len(body) > 0
        ):
            preview = _clean_text(root.get_text(" ", strip=True))[:220]
            return {
                "chunks": [],
                "error": (
                    f"No substantive HTML text; HTTP {status}; content-type={content_type}; "
                    f"title={title}; response length={len(body)}; preview={preview!r}"
                ),
            }

        chunks, current = [], ""
        for piece in pieces:
            if current and len(current) + len(piece) + 1 > 1800:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n{piece}" if current else piece
        if current:
            chunks.append(current)

        if not chunks:
            preview = _clean_text(root.get_text(" ", strip=True))[:220]
            return {
                "chunks": [],
                "error": (
                    f"No readable page text; HTTP {status}; content-type={content_type}; "
                    f"title={title}; response length={len(body)}; preview={preview!r}"
                ),
            }
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
    """Fetch each approved page afresh so a temporary block is not cached."""
    fetched_sources = []
    for source in INDIA_SOURCES:
        fetched = _fetch_source(source["url"])
        fetched_sources.append({**source, **fetched})
    return fetched_sources


def retrieve_india_context(question: str, max_chunks: int = 6):
    """Return relevant text and source labels from the four approved pages only."""
    query_terms = _terms(question)
    query_counts = Counter(query_terms)
    ranked = []
    errors = []
    fetched_sources = _fetch_all_sources()

    for source in fetched_sources:
        if source.get("error"):
            errors.append(f"{source['name']}: {source['error']}")
            continue
        for chunk in source.get("chunks", []):
            chunk_terms = Counter(_terms(chunk))
            overlap = sum(min(count, chunk_terms.get(term, 0)) for term, count in query_counts.items())
            score = overlap / max(1, len(set(query_terms)))
            if score > 0:
                ranked.append((score, source, chunk))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[:max_chunks]

    # If the pages were fetched successfully but keyword overlap is zero, use a
    # bounded sample from those same pages rather than claiming retrieval failed.
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
    for _, source, chunk in selected:
        context_parts.append(f"SOURCE: {source['name']}\nURL: {source['url']}\n{chunk}")
        if source["url"] not in source_urls:
            source_urls.append(source["url"])

    return {
        "context": "\n\n---\n\n".join(context_parts),
        "sources": source_urls,
        "errors": errors,
    }

