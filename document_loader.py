import os
import pdfplumber

BASE_DIR = "data/documents"

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


def load_all_documents(country, doc_type):
    print(f"\n📂 Loading documents for: {country} - {doc_type}")
    print("─" * 50)

    documents = load_pdfs(country, doc_type)

    print(f"\n📊 Total documents loaded: {len(documents)}")
    return documents


if __name__ == "__main__":
    docs = load_all_documents("uae", "aml")
    for doc in docs[:3]:
        print(f"\nSource: {doc['source']}")
        print(f"Text: {doc['text'][:200]}...")
