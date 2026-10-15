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
def get_answer(question, vectorstore):
    # Setup APIs
    groq_key, gemini_key = setup_apis()

    # Search documents
    results = vectorstore.similarity_search(question, k=5)

    # Nothing found
    if not results:
        return {
            "answer": "I could not find any relevant information in the available documents.",
            "sources": [],
        }

    # Build context
    context = "\n\n".join([r.page_content for r in results])

    # Collect unique sources
    sources = list(set([
        r.metadata.get("source_file", r.metadata.get("source", "Unknown"))
        for r in results
    ]))

    # Try Groq first
    answer = ask_groq(question, context, groq_key)

    # If Groq fails try Gemini
    if not answer:
        answer = ask_gemini(question, context)

    # If both fail
    if not answer:
        answer = "I was unable to generate an answer. Please try again."

    return {
        "answer": answer,
        "sources": sources,
    }
