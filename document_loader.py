import os
import json
import pdfplumber
import requests
from bs4 import BeautifulSoup

# ── Base path ──────────────────────────────────────────────
BASE_DIR = "data/documents"

# ──────────────────────────────────────────────────────────
# 1. LOAD PDFs
# ──────────────────────────────────────────────────────────
def load_pdfs(country, doc_type):
    """
    Reads all PDFs from data/documents/{country}/{doc_type}/
    Returns list of dicts with text + metadata
    """
    documents = []
    folder = os.path.join(BASE_DIR, country, doc_type)

    # Folder does not exist
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
# 2. SCRAPE LINKS
# ──────────────────────────────────────────────────────────
def scrape_links(country, doc_type):
    """
    Reads links.json and scrapes all links
    for the given country + doc_type
    Returns list of dicts with text + metadata
    """
    documents = []

    # Load links.json
    try:
        with open("links.json", "r") as f:
            all_links = json.load(f)
    except Exception as e:
        print(f"❌ Could not read links.json: {e}")
        return documents

    # Get links for this country + type
    links = all_links.get(country, {}).get(doc_type, [])

    if not links:
        print(f"No links found for {country} - {doc_type}")
        return documents

    for url in links:
        print(f"Scraping: {url}")
        try:
            response = requests.get(url, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove navigation and footer noise
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            text = soup.get_text(separator="\n")

            # Clean up blank lines
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            clean_text = "\n".join(lines)

            if clean_text:
                documents.append({
                    "text": clean_text,
                    "source": url,
                    "country": country,
                    "type": doc_type
                })
                print(f"✅ Scraped: {url}")
            else:
                print(f"⚠️ No text found at: {url}")

        except Exception as e:
            print(f"❌ Error scraping {url}: {e}")

    return documents


# ──────────────────────────────────────────────────────────
# 3. LOAD ALL DOCUMENTS
# ──────────────────────────────────────────────────────────
def load_all_documents(country, doc_type):
    """
    Combines PDFs + Links for given country + type
    Returns one list of all documents
    """
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
# 4. QUICK TEST
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    docs = load_all_documents("uk", "aml")

    print("\n── Sample Output ──")
    for doc in docs:
        print(f"\nSource  : {doc['source']}")
        print(f"Country : {doc['country']}")
        print(f"Type    : {doc['type']}")
        print(f"Text    : {doc['text'][:200]}...")
