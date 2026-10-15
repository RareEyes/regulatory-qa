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


def _normalise_country(value):
    """Normalize country labels that may differ across the UI and FAISS metadata."""
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "united_kingdom": "uk", "great_britain": "uk", "britain": "uk",
        "ksa": "saudi_arabia", "saudi": "saudi_arabia",
        "uae": "uae", "united_arab_emirates": "uae",
        "india": "india", "all": "all",
    }
    return aliases.get(text, text)


def _metadata_country_matches(metadata, requested_country):
    """Match the requested country using country metadata first, then source path."""
    wanted = _normalise_country(requested_country)
    if wanted == "all":
        return True

    candidates = [metadata.get("country", "")]
    # Older index records may lack a country field but retain the folder/source path.
    candidates.extend([
        metadata.get("source_file", ""),
        metadata.get("source", ""),
        metadata.get("file_path", ""),
    ])
    for candidate in candidates:
        normalized = _normalise_country(candidate)
        if normalized == wanted:
            return True
        # Match country folder names in paths such as data/documents/uk/...
        path_parts = str(candidate or "").replace("\\", "/").lower().split("/")
        if any(_normalise_country(part) == wanted for part in path_parts):
            return True
    return False


def get_answer(question, vectorstore, country="All"):
    # India uses only the four user-approved website URLs. No links found on those
    # pages are followed, and no India PDF/FAISS results are mixed into the answer.
    if _normalise_country(country) == "india":
        retrieved = retrieve_india_context(question)
        if not retrieved["context"].strip():
            message = "I could not retrieve usable text from the four approved India regulatory pages."
            if retrieved["errors"]:
                message += " Fetch details: " + " | ".join(retrieved["errors"])
            return {"answer": message, "sources": []}

        groq_key, gemini_key = setup_apis()
        # India uses live webpage context. Keep its generation errors visible so a
        # provider/context failure can be diagnosed without affecting other countries.
        generation_errors = []
        answer = None
        try:
            if not groq_key:
                raise RuntimeError("GROQ_API_KEY is not configured")
            client = Groq(api_key=groq_key)
            response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[{"role": "user", "content": build_prompt(question, retrieved["context"])}],
                temperature=0.2,
            )
            answer = response.choices[0].message.content
            if not answer:
                generation_errors.append("Groq returned an empty answer")
        except Exception as exc:
            generation_errors.append(f"Groq: {type(exc).__name__}: {exc}")

        if not answer:
            try:
                if not gemini_key:
                    raise RuntimeError("GEMINI_API_KEY is not configured")
                model = genai.GenerativeModel("gemini-3.8-flash")
                response = model.generate_content(build_prompt(question, retrieved["context"]))
                answer = getattr(response, "text", None)
                if not answer:
                    generation_errors.append("Gemini returned no text")
            except Exception as exc:
                generation_errors.append(f"Gemini: {type(exc).__name__}: {exc}")

        if not answer:
            answer = "India answer generation failed. Diagnostic details: " + " | ".join(generation_errors)
        return {"answer": answer, "sources": retrieved["sources"]}

    # Keep the existing PDF/FAISS workflow for UK, UAE and Saudi Arabia, but NEVER
    # fall back to another country's results when a country filter returns no match.
    groq_key, _ = setup_apis()
    all_results = vectorstore.similarity_search(question, k=30)

    if _normalise_country(country) != "all":
        results = [
            result for result in all_results
            if _metadata_country_matches(result.metadata, country)
        ]
    else:
        results = all_results[:5]

    if not results:
        return {
            "answer": (
                f"I could not find relevant information in the indexed sources for {country}. "
                "No sources from other countries were used. Check that this country's documents "
                "have the correct country metadata or are stored under the matching country folder."
            ),
            "sources": [],
        }

    results = results[:5]
    context = "\n\n".join(result.page_content for result in results)
    sources = list(dict.fromkeys(
        result.metadata.get("source_file", result.metadata.get("source", "Unknown"))
        for result in results
    ))
    answer = _generate_answer(question, context, groq_key)
    return {"answer": answer, "sources": sources}
