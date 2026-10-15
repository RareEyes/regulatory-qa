"""Retrieve India regulatory text from only the four user-approved URLs.

This module fetches the pages themselves. It never follows links found inside
those pages and does not download linked PDFs or other documents.
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ComplianceShelfResearch/1.0)",
    "Accept": "text/html,application/xhtml+xml",
}


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_source(url: str):
    """Fetch one exact URL; do not crawl links on the page."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove page furniture, scripts and forms; never inspect or request hrefs.
        for element in soup.find_all(
            ["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]
        ):
            element.decompose()

        root = soup.find("main") or soup.find("article") or soup.body or soup
        pieces = []
        for element in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td"]):
            text = re.sub(r"\s+", " ", element.get_text(" ", strip=True)).strip()
            if len(text) >= 35 and text not in pieces:
                pieces.append(text)

        # Fallback for pages that don't use standard paragraph elements.
        if not pieces:
            fallback = re.sub(r"\s+", " ", root.get_text(" ", strip=True)).strip()
            if fallback:
                pieces = [fallback]

        # Group neighbouring paragraphs into useful, bounded retrieval chunks.
        chunks, current = [], ""
        for piece in pieces:
            if current and len(current) + len(piece) + 1 > 1800:
                chunks.append(current)
                current = piece
            else:
                current = f"{current}\n{piece}" if current else piece
        if current:
            chunks.append(current)
        return {"chunks": chunks, "error": None}
    except Exception as exc:
        return {"chunks": [], "error": f"{type(exc).__name__}: {exc}"}


def _terms(text: str):
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    stop = {
        "the", "and", "for", "with", "from", "that", "this", "what", "when",
        "where", "which", "who", "how", "does", "under", "are", "is", "to",
        "of", "in", "on", "a", "an", "or", "by", "be", "it", "as", "at",
        "can", "could", "should", "would", "please", "india", "rbi", "sebi",
    }
    return [word for word in words if len(word) > 2 and word not in stop]


def retrieve_india_context(question: str, max_chunks: int = 6):
    """Return relevant text and source labels from the four approved pages only."""
    query_terms = _terms(question)
    query_counts = Counter(query_terms)
    ranked = []
    errors = []

    for source in INDIA_SOURCES:
        fetched = _fetch_source(source["url"])
        if fetched["error"]:
            errors.append(f"{source['name']}: {fetched['error']}")
            continue
        for chunk in fetched["chunks"]:
            chunk_terms = Counter(_terms(chunk))
            overlap = sum(min(count, chunk_terms.get(term, 0)) for term, count in query_counts.items())
            # Give a modest preference to chunks with a higher proportion of query terms.
            score = overlap / max(1, len(set(query_terms)))
            if score > 0:
                ranked.append((score, source, chunk))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[:max_chunks]

    context_parts = []
    source_labels = []
    for _, source, chunk in selected:
        context_parts.append(f"SOURCE: {source['name']}\nURL: {source['url']}\n{chunk}")
        if source["url"] not in source_labels:
            source_labels.append(source["url"])

    return {
        "context": "\n\n---\n\n".join(context_parts),
        "sources": source_labels,
        "errors": errors,
    }
