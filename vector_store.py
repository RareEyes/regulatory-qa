import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

# ──────────────────────────────────────────────────────────
# 1. SPLIT DOCUMENTS INTO CHUNKS
# ──────────────────────────────────────────────────────────
def split_documents(documents):
    """
    Splits large documents into smaller chunks
    Each chunk keeps its metadata (source, country, type)
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )

    chunks = []
    for doc in documents:
        splits = splitter.split_text(doc["text"])
        for split in splits:
            chunks.append({
                "text": split,
                "source": doc["source"],
                "country": doc["country"],
                "type": doc["type"]
            })

    print(f"✅ Total chunks created: {len(chunks)}")
    return chunks


# ──────────────────────────────────────────────────────────
# 2. CREATE FAISS INDEX
# ──────────────────────────────────────────────────────────
def create_vector_store(chunks):
    """
    Creates FAISS vector store from chunks
    Uses HuggingFace embeddings (free, no API key needed)
    """
    print("⏳ Creating embeddings... please wait")

    # Free embeddings - no API key needed
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    texts = [c["text"] for c in chunks]
    metadatas = [
        {
            "source": c["source"],
            "country": c["country"],
            "type": c["type"]
        }
        for c in chunks
    ]

    vector_store = FAISS.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas
    )

    print("✅ Vector store created successfully!")
    return vector_store


# ──────────────────────────────────────────────────────────
# 3. SEARCH VECTOR STORE
# ──────────────────────────────────────────────────────────
def search_documents(vector_store, question, country, doc_type, k=5):
    """
    Step 1: Search selected country + type
    Step 2: If no results, search all docs in same country
    Step 3: If still nothing, stop
    """
    # Step 1 - Search selected country + type
    results = vector_store.similarity_search(
        question,
        k=k,
        filter={"country": country, "type": doc_type}
    )

    if results:
        print(f"✅ Found in {country} - {doc_type}")
        return results, "exact"

    # Step 2 - Search all docs in same country
    print(f"⚠️ Nothing in {doc_type}, searching all {country} docs...")
    results = vector_store.similarity_search(
        question,
        k=k,
        filter={"country": country}
    )

    if results:
        print(f"✅ Found in {country} - different type")
        return results, "country_wide"

    # Step 3 - Nothing found
    print(f"❌ Nothing found for {country}")
    return [], "not_found"


# ──────────────────────────────────────────────────────────
# 4. QUICK TEST
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    from document_loader import load_all_documents

    docs = load_all_documents("uk", "aml")
    chunks = split_documents(docs)
    vector_store = create_vector_store(chunks)

    results, status = search_documents(
        vector_store,
        "What are the AML requirements?",
        "uk",
        "aml"
    )

    print(f"\nSearch Status: {status}")
    print(f"Results Found: {len(results)}")
    if results:
        print(f"\nTop Result:\n{results[0].page_content[:300]}")
