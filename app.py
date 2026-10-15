import streamlit as st
from document_loader import load_all_documents
from vector_store import get_vectorstore
from qa_chain import get_answer

# ──────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Regulatory Q&A",
    page_icon="⚖️",
    layout="wide"
)

# ──────────────────────────────────────────────────────────
# LOAD VECTOR STORE (cached so it runs only once)
# ──────────────────────────────────────────────────────────
@st.cache_resource
def load_vector_store(country, doc_type):
    docs = load_all_documents(country, doc_type)
    if not docs:
        return None
    chunks = split_documents(docs)
    vector_store = create_vector_store(chunks)
    return vector_store

# ──────────────────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚖️ Regulatory Q&A")
    st.markdown("---")

    country = st.selectbox(
        "🌍 Select Country",
        ["uk", "uae", "india", "saudi_arabia"],
        format_func=lambda x: {
            "uk": "🇬🇧 United Kingdom",
            "uae": "🇦🇪 UAE",
            "india": "🇮🇳 India",
            "saudi_arabia": "🇸🇦 Saudi Arabia"
        }[x]
    )

    doc_type = st.selectbox(
        "📋 Select Type",
        ["aml", "banking", "insurance", "others"],
        format_func=lambda x: x.upper()
    )

    st.markdown("---")

    if st.button("🗑️ Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

# ──────────────────────────────────────────────────────────
# MAIN AREA
# ──────────────────────────────────────────────────────────
st.title("⚖️ Regulatory Q&A")
st.markdown("*Your AI-powered regulatory research assistant*")
st.markdown("---")

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display chat history
for chat in st.session_state.chat_history:
    with st.chat_message("user"):
        st.write(chat["question"])
    with st.chat_message("assistant"):
        st.write(chat["answer"])
        if chat["sources"]:
            st.markdown("**📚 Sources:**")
            for source in chat["sources"]:
                st.markdown(f"- {source}")
        if chat["search_status"] == "country_wide":
            st.warning("⚠️ Answer found in different document type!")

# ──────────────────────────────────────────────────────────
# QUESTION INPUT
# ──────────────────────────────────────────────────────────
question = st.chat_input("Ask your regulatory question here...")

if question:
    # Load vector store
    with st.spinner("⏳ Loading documents..."):
        vector_store = load_vector_store(country, doc_type)

    if vector_store is None:
        st.error(f"❌ No documents found for {country.upper()} - {doc_type.upper()}")
    else:
        # Get answer
        with st.spinner("⏳ Finding answer..."):
            result = get_answer(
                question,
                vector_store,
                country,
                doc_type
            )

        # Display answer
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            st.write(result["answer"])
            if result["sources"]:
                st.markdown("**📚 Sources:**")
                for source in result["sources"]:
                    st.markdown(f"- {source}")
            if result["search_status"] == "country_wide":
                st.warning("⚠️ Answer found in different document type!")

        # Save to chat history
        st.session_state.chat_history.append({
            "question": question,
            "answer": result["answer"],
            "sources": result["sources"],
            "search_status": result["search_status"]
        })
