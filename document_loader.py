import os
import json
import pdfplumber
import requests
from bs4 import BeautifulSoup

# ── Base path ──────────────────────────────────────────────
BASE_DIR = "data/documents"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (CHROME/91.0) Safari/537.36"
}

# ──────────────────────────────────────────────────────────
# 1. LOAD PDFs
# ──────────────────────────────────────────────────────────
def load_pdfs(country, doc_type):
    documents = []
    folder = os.path.join(BASE_DIR, country, doc_type)

    if not os.path.exists(folder):
        print(f"Folder not found: {folder}")
        return documents

    for filename in os.listdir(folder):
        if filename.endswith(".pdf"):
            filepath = os.path.join(folder, filename)
            print(f"Reading PDF: {filename}")
            try:
                text = ""
                with pdfplumber.open(filepath) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"

                if text.strip():
                    documents.append({
                        "text": text,
                        "source": filename,
                        "country": country,
                        "type": doc_type
                    })
                    print(f"✅ Loaded: {filename}")
                else:
                    print(f"⚠️ No text found in: {filename}")

            except Exception as e:
                print(f"❌ Error reading {filename}: {e}")

    return documents


# ──────────────────────────────────────────────────────────
# 2. SCRAPE SINGLE PAGE
# ──────────────────────────────────────────────────────────
def scrape_page(url):
    """
    Scrapes a single page and returns clean text
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"⚠️ Status {response.status_code} for {url}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        clean_text = "\n".join(lines)

        return clean_text if clean_text else None

    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return None


# ──────────────────────────────────────────────────────────
# 3. GET SUB LINKS
# ──────────────────────────────────────────────────────────
def get_sub_links(url):
    """
    Finds all sub links inside a page
    Only returns links from same domain
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        # Get base domain
        from urllib.parse import urlparse, urljoin
        base = urlparse(url)
        base_domain = f"{base.scheme}://{base.netloc}"

        sub_links = []
        for a in soup.find_all("a", href=True):
            href = a['href']

            # Skip javascript and anchors
            if href.startswith("javascript") or href.startswith("#"):
                continue

            # Make full URL if relative
            if href.startswith("/"):
                href = base_domain + href

            # Only keep same domain links
            if base_domain in href and href != url:
                sub_links.append(href)

        # Remove duplicates
        sub_links = list(set(sub_links))
        print(f"Found {len(sub_links)} sub-links in {url}")
        return sub_links

    except Exception as e:
        print(f"❌ Error getting sub-links: {e}")
        return []


# ──────────────────────────────────────────────────────────
# 4. DEEP SCRAPE
# ──────────────────────────────────────────────────────────
def deep_scrape(url, country, doc_type):
    """
    Scrapes main page + all sub links
    Returns list of documents
    """
    documents = []

    print(f"\n🔍 Deep scraping: {url}")

    # Get all sub links first
    sub_links = get_sub_links(url)

    # Add main url to scrape
    all_urls = [url] + sub_links
    print(f"Total pages to scrape: {len(all_urls)}")

    for page_url in all_urls:
        print(f"Scraping: {page_url}")
        text = scrape_page(page_url)

        if text:
            documents.append({
                "text": text,
                "source": page_url,
                "country": country,
                "type": doc_type
            })
            print(f"✅ Scraped: {page_url}")

    return documents


# ──────────────────────────────────────────────────────────
# 5. SCRAPE ALL LINKS
# ──────────────────────────────────────────────────────────
def scrape_links(country, doc_type):
    documents = []

    try:
        with open("links.json", "r") as f:
            all_links = json.load(f)
    except Exception as e:
        print(f"❌ Could not read links.json: {e}")
        return documents

    links = all_links.get(country, {}).get(doc_type, [])

    if not links:
        print(f"No links found for {country} - {doc_type}")
        return documents

    for url in links:
        docs = deep_scrape(url, country, doc_type)
        documents.extend(docs)

    return documents


# ──────────────────────────────────────────────────────────
# 6. LOAD ALL DOCUMENTS
# ──────────────────────────────────────────────────────────
def load_all_documents(country, doc_type):
    print(f"\n📂 Loading documents for: {country} - {doc_type}")
    print("─" * 50)

    pdf_docs  = load_pdfs(country, doc_type)
    link_docs = scrape_links(country, doc_type)

    all_docs = pdf_docs + link_docs

    print(f"\n📊 Total documents loaded: {len(all_docs)}")
    print(f"   PDFs  : {len(pdf_docs)}")
    print(f"   Links : {len(link_docs)}")

    return all_docs


# ──────────────────────────────────────────────────────────
# 7. QUICK TEST
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    docs = load_all_documents("uae", "banking")
    print("\n── Sample Output ──")
    for doc in docs[:3]:
        print(f"\nSource  : {doc['source']}")
        print(f"Text    : {doc['text'][:200]}...")
