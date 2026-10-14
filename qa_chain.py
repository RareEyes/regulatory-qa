import os
from groq import Groq
import google.generativeai as genai

# ──────────────────────────────────────────────────────────
# 1. SETUP API KEYS
# ──────────────────────────────────────────────────────────
def setup_apis():
    """
    Gets API keys from Streamlit secrets or environment
    """
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
def build_prompt(question, context, country, doc_type):
    """
    Builds prompt from question + context
    """
    return f"""You are a regulatory expert for {country.upper()} {doc_type.upper()} regulations.

Use ONLY the context below to answer the question.
If the answer is not in the context, say "I could not find this in the available documents."

Context:
{context}

Question: {question}

Answer:"""


# ──────────────────────────────────────────────────────────
# 3. ASK GROQ (PRIMARY)
# ──────────────────────────────────────────────────────────
def ask_groq(question, context, country, doc_type, groq_key):
    """
    Primary LLM = Groq
    Fast and reliable
    """
    try:
        client = Groq(api_key=groq_key)
        prompt = build_prompt(question, context, country, doc_type)

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
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
def ask_gemini(question, context, country, doc_type):
    """
    Backup LLM = Gemini
    Only used if Groq fails
    """
    try:
        prompt = build_prompt(question, context, country, doc_type)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        print(f"⚠️ Gemini failed: {e}")
        return None


# ──────────────────────────────────────────────────────────
# 5. MAIN QA FUNCTION
# ──────────────────────────────────────────────────────────
def get_answer(question, vector_store, country, doc_type):
    """
    Main function:
    1. Search documents
    2. Build context
    3. Ask Groq first
    4. If Groq fails, ask Gemini
    5. Return answer + sources + status
    """
    from vector_store import search_documents

    # Setup APIs
    groq_key, gemini_key = setup_apis()

    # Search documents
    results, search_status = search_documents(
        vector_store, question, country, doc_type
    )

    # Nothing found
    if search_status == "not_found" or not results:
        return {
            "answer": "I could not find any relevant information in the available documents.",
            "sources": [],
            "search_status": "not_found",
            "llm_used": None
        }

    # Build context from results
    context = "\n\n".join([r.page_content for r in results])

    # Collect unique sources
    sources = list(set([r.metadata["source"] for r in results]))

    # Try Groq first
    answer = ask_groq(question, context, country, doc_type, groq_key)
    llm_used = "Groq"

    # If Groq fails try Gemini
    if not answer:
        print("⚠️ Trying Gemini as backup...")
        answer = ask_gemini(question, context, country, doc_type)
        llm_used = "Gemini"

    # If both fail
    if not answer:
        answer = "I was unable to generate an answer. Please try again."
        llm_used = None

    return {
        "answer": answer,
        "sources": sources,
        "search_status": search_status,
        "llm_used": llm_used
    }
