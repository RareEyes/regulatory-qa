import streamlit as st
from vector_store import get_vectorstore
from qa_chain import get_answer

# ──────────────────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Regulatory Q&A",
    page_icon="⚖️",
    layout="centered"
)

# ──────────────────────────────────────────────────────────
# LOAD VECTOR STORE ONCE
# ──────────────────────────────────────────────────────────
vectorstore = get_vectorstore()

# ──────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────
st.markdown("<h1 style='text-align: center;'>⚖️ Regulatory Q&A</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Your AI-powered regulatory research assistant</p>", unsafe_allow_html=True)
st.markdown("---")

# ──────────────────────────────────────────────────────────
# COUNTRY FILTER
# ──────────────────────────────────────────────────────────
country = st.selectbox(
    "🌍 Select Country",
    ["All", "United Kingdom", "UAE", "India", "Saudi Arabia"]
)

# ──────────────────────────────────────────────────────────
# CLEAR CHAT
# ──────────────────────────────────────────────────────────
if st.button("🗑️ Clear Chat History"):
    st.session_state.chat_history = []
    st.rerun()

st.markdown("---")

# ──────────────────────────────────────────────────────────
# CHAT HISTORY
# ──────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for chat in st.session_state.chat_history:
    with st.chat_message("user"):
        st.write(chat["question"])
    with st.chat_message("assistant"):
        st.write(chat["answer"])
        if chat["sources"]:
            st.markdown("**📚 Sources:**")
            for source in chat["sources"]:
                st.markdown(f"- {source}")

# ──────────────────────────────────────────────────────────
# QUESTION INPUT
# ──────────────────────────────────────────────────────────
question = st.chat_input("Ask your regulatory question here...")

if question:
    with st.spinner("⏳ Finding answer..."):
        result = get_answer(question, vectorstore)

    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        st.write(result["answer"])
        if result["sources"]:
            st.markdown("**📚 Sources:**")
            for source in result["sources"]:
                st.markdown(f"- {source}")

    st.session_state.chat_history.append({
        "question": question,
        "answer": result["answer"],
        "sources": result["sources"]
    })
