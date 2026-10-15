import os
from groq import Groq
import google.generativeai as genai
from india_web import retrieve_india_context


def setup_apis():
    try:
        import streamlit as st
        groq_key = st.secrets["GROQ_API_KEY"]
        gemini_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        groq_key = os.getenv("GROQ_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")

    genai.configure(api_key=gemini_key)
    return groq_key, gemini_key


def build_prompt(question, context):
    return f"""You are a regulatory research assistant for Compliance Shelf.

Use ONLY the source context below to answer. Do not add requirements from general knowledge.
If the source context does not support the answer, say: "I could not find this in the available India regulatory pages."
Clearly distinguish requirements from examples or explanations. Do not infer missing legal obligations.

Context:
{context}

Question: {question}

Answer:"""


def ask_groq(question, context, groq_key):
    try:
        client = Groq(api_key=groq_key)
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "user", "content": build_prompt(question, context)}],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as exc:
        print(f"Groq failed: {exc}")
        return None


def ask_gemini(question, context):
    try:
        model = genai.GenerativeModel("gemini-3.8-flash")
        response = model.generate_content(build_prompt(question, context))
        return response.text
    except Exception as exc:
        print(f"Gemini failed: {exc}")
        return None


def _generate_answer(question, context, groq_key):
    answer = ask_groq(question, context, groq_key)
    if not answer:
        answer = ask_gemini(question, context)
    return answer or "I was unable to generate an answer. Please try again."


def get_answer(question, vectorstore, country="All"):
    # India uses only the four user-approved website URLs. No links found on those
    # pages are followed, and no India PDF/FAISS results are mixed into the answer.
    if str(country).strip().lower() == "india":
        retrieved = retrieve_india_context(question)
        if not retrieved["context"].strip():
            message = "I could not retrieve relevant text from the four approved India regulatory pages."
            if retrieved["errors"]:
                message += " Fetch errors: " + " | ".join(retrieved["errors"])
            return {"answer": message, "sources": []}

        groq_key, _ = setup_apis()
        answer = _generate_answer(question, retrieved["context"], groq_key)
        # SEBI's supplied page may expose only the circular title and a document link;
        # because link-following is disabled, the answer is limited to page text fetched.
        return {"answer": answer, "sources": retrieved["sources"]}

    # Existing PDF/FAISS workflow for All, UK, UAE and Saudi Arabia is retained.
    groq_key, _ = setup_apis()
    all_results = vectorstore.similarity_search(question, k=20)

    if country != "All":
        results = [
            result for result in all_results
            if result.metadata.get("country", "").lower() == country.lower()
        ]
        if not results:
            results = all_results[:5]
    else:
        results = all_results[:5]

    if not results:
        return {"answer": "I could not find any relevant information.", "sources": []}

    context = "\n\n".join(result.page_content for result in results)
    sources = list(set(
        result.metadata.get("source_file", result.metadata.get("source", "Unknown"))
        for result in results
    ))
    answer = _generate_answer(question, context, groq_key)
    return {"answer": answer, "sources": sources}
