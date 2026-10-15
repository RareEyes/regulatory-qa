import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import streamlit as st

FAISS_INDEX_PATH = "faiss_index"
EMBEDDING_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"

@st.cache_resource(show_spinner="Loading knowledge base...")
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )

@st.cache_resource(show_spinner="Loading knowledge base...")
def get_vectorstore():
    embeddings = get_embeddings()
    vectorstore = FAISS.load_local(
        FAISS_INDEX_PATH,
        embeddings,
        allow_dangerous_deserialization=True
    )
    return vectorstore
