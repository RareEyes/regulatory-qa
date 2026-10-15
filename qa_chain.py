import os
from groq import Groq
import google.generativeai as genai

# ──────────────────────────────────────────────────────────
# 1. SETUP API KEYS
# ──────────────────────────────────────────────────────────
def setup_apis():
    try:
        import streamlit as st
        groq_key = st.secrets["GROQ_API_KEY"]
        gemini_key = st.secrets["GEMINI_API_KEY"]
    except:
        groq_key = os.getenv("GROQ_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")

    genai.configure(api_key=gemini_key)
    return groq_key, gemini_key


# ──────────────────────────────────────────────────────────
# 2. BUILD PROMPT
# ──────────────────────────────────────────────────────────
def build_prompt(question, context):
    return f"""You are a regulatory expert assistant.

Use ONLY the context below to answer the question.
If the answer is not in the context, say "I could not find this in the available documents."

Context:
{context}

Question: {question}

Answer:"""


# ──────────────────────────────────────────────────────────
# 3. ASK GROQ (PRIMARY)
# ──────────────────────────────────────────────────────────
def ask_groq(question, context, groq_key):
    try:
        client = Groq(api_key=groq_key)
        prompt = build_prompt(question, context)

        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"⚠️ Groq failed: {e}")
        return None


# ──────────────────────────────────────────────────────────
# 4. ASK GEMINI (BACKUP)
# ──────────────────────────────────────────────────────────
def ask_gemini(question, context):
    try:
        prompt = build_prompt(question, context)
        model = genai.GenerativeModel("gemini-3.8-flash")
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        print(f"⚠️ Gemini failed: {e}")
        return None


# ──────────────────────────────────────────────────────────
# 5. MAIN QA FUNCTION
# ──────────────────────────────────────────────────────────
def _normalize_country(value):
    """Normalize country labels stored in document metadata."""
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


COUNTRY_ALIASES = {
    "united kingdom": {"united kingdom", "uk", "great britain"},
    "uae": {"uae", "united arab emirates"},
    "india": {"india"},
    "saudi arabia": {"saudi arabia", "saudi"},
}


def get_answer(question, vectorstore, country="All"):
    # Setup APIs
    groq_key, gemini_key = setup_apis()

    # Retrieve a wider set first, then strictly filter by country.
    # Never fall back to unfiltered results for a selected country.
    all_results = vectorstore.similarity_search(question, k=100)

    if country != "All":
        selected = _normalize_country(country)
        allowed_values = COUNTRY_ALIASES.get(selected, {selected})
        results = [
            doc for doc in all_results
            if _normalize_country(doc.metadata.get("country", "")) in allowed_values
        ]
    else:
        results = all_results[:5]

    if not results:
        if country != "All":
            return {
                "answer": (
                    f"I could not find relevant information in the available "
                    f"{country} documents. Please check that the documents in "
                    f"that country's folder were included in the FAISS index "
                    f"and have a 'country' metadata field."
                ),
                "sources": [],
            }
        return {
            "answer": "I could not find any relevant information.",
            "sources": [],
        }

    # Limit the context for selected-country searches as well.
    results = results[:5]

    # Build context only from the filtered documents.
    context = "\\n\\n".join([doc.page_content for doc in results])

    # The loader stores the filename under 'source'; older indexes may use
    # 'source_file', so support both.
    sources = sorted(set(
        doc.metadata.get("source_file")
        or doc.metadata.get("source")
        or "Unknown"
        for doc in results
    ))

    # Try Groq first
    answer = ask_groq(question, context, groq_key)

    # If Groq fails try Gemini
    if not answer:
        answer = ask_gemini(question, context)

    if not answer:
        answer = "I was unable to generate an answer. Please try again."

    return {
        "answer": answer,
        "sources": sources,
    }
