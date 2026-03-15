"""
Streamlit App - Arabic RAG Interface.
Upload a page-structured Arabic .txt file, ask a question, get a grounded answer.
"""

import os
import streamlit as st
from rag import build_index, retrieve, generate_answer

# ----------------------------
# Page Configuration
# ----------------------------
st.set_page_config(
    page_title="Arabic RAG",
    page_icon="🔍",
    layout="centered",
)

# ----------------------------
# Custom CSS
# ----------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Tajawal:wght@300;400;700&display=swap');

    :root {
        --bg:       #0d0f14;
        --surface:  #151820;
        --border:   #252a36;
        --accent:   #4fffb0;
        --accent2:  #a78bfa;
        --text:     #e8eaf0;
        --muted:    #6b7280;
    }

    html, body, [class*="css"] {
        background-color: var(--bg) !important;
        color: var(--text) !important;
        font-family: 'Tajawal', sans-serif;
    }

    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 3rem; max-width: 760px; }

    /* Inputs */
    .stTextInput input,
    .stTextArea textarea {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text) !important;
        font-family: 'Tajawal', sans-serif !important;
        font-size: 1.05rem !important;
        direction: rtl;
    }
    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 2px rgba(79,255,176,0.12) !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        background: var(--surface) !important;
        border: 1px dashed var(--border) !important;
        border-radius: 10px !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: var(--accent) !important;
    }

    /* Ask button */
    .stButton > button {
        width: 100%;
        background: var(--accent) !important;
        color: #0d0f14 !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        padding: 0.6rem 1rem !important;
        margin-top: 0.3rem;
        transition: opacity 0.15s !important;
    }
    .stButton > button:hover { opacity: 0.85 !important; }
    .stButton > button:disabled { opacity: 0.35 !important; }

    /* Download button */
    .stDownloadButton > button {
        background: transparent !important;
        border: 1px solid var(--accent2) !important;
        color: var(--accent2) !important;
        border-radius: 8px !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.82rem !important;
        padding: 0.4rem 1rem !important;
    }
    .stDownloadButton > button:hover {
        background: var(--accent2) !important;
        color: #0d0f14 !important;
    }

    /* Answer box */
    .answer-box {
        background: var(--surface);
        border: 1px solid var(--accent);
        border-left: 4px solid var(--accent);
        border-radius: 10px;
        padding: 1.4rem 1.6rem;
        direction: rtl;
        font-size: 1.08rem;
        line-height: 1.95;
        margin-top: 0.5rem;
        white-space: pre-wrap;
    }

    /* Page chunk card */
    .chunk-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 0.85rem 1.1rem;
        margin-bottom: 0.55rem;
        direction: rtl;
        font-size: 0.9rem;
        line-height: 1.75;
        color: #94a3b8;
    }
    .chunk-header {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        color: var(--accent2);
        margin-bottom: 0.4rem;
        display: flex;
        justify-content: space-between;
    }

    /* Section label */
    .label {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.73rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 0.4rem;
        margin-top: 1.4rem;
    }

    /* Hero */
    .hero { margin-bottom: 2.2rem; }
    .hero-title {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.55rem;
        font-weight: 600;
        color: var(--accent);
    }
    .hero-sub {
        color: var(--muted);
        font-size: 0.9rem;
        margin-top: 0.25rem;
    }

    hr { border-color: var(--border) !important; margin: 1.4rem 0 !important; }

    /* Status pill */
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.22rem 0.75rem;
        border-radius: 99px;
        font-size: 0.75rem;
        font-family: 'IBM Plex Mono', monospace;
    }
    .pill-green { background: rgba(79,255,176,0.1); color: var(--accent); border: 1px solid rgba(79,255,176,0.25); }
    .pill-red { background: rgba(255,107,107,0.1); color: #ff6b6b; border: 1px solid rgba(255,107,107,0.25); }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Load API key from .env
# ----------------------------

# ----------------------------
# Hero Header
# ----------------------------
st.markdown("""
<div class="hero">
  <div class="hero-title">Arabic RAG Assistant 🔍</div>
  <div class="hero-sub">Upload your document and ask any question</div>
</div>
""", unsafe_allow_html=True)

# ----------------------------
# File Upload
# ----------------------------
st.markdown('<div class="label">Document</div>', unsafe_allow_html=True)
uploaded_file = st.file_uploader(
    label="Upload .txt",
    type=["txt"],
    label_visibility="collapsed",
)

# ----------------------------
# Index Building
# ----------------------------
index = None
page_chunks = None
embed_model = None

if uploaded_file:
    file_content = uploaded_file.read().decode("utf-8")

    try:
        with st.spinner("Building index from pages..."):
            index, page_chunks, embed_model = build_index(file_content)

        st.markdown(
            f'<span class="pill pill-green">✓ {len(page_chunks)} pages indexed</span>',
            unsafe_allow_html=True,
        )
    except ValueError as e:
        st.markdown(
            f'<span class="pill pill-red">⚠ {e}</span>',
            unsafe_allow_html=True,
        )

# ----------------------------
# Question Input
# ----------------------------
st.markdown('<div class="label">Question</div>', unsafe_allow_html=True)
query = st.text_area(
    label="Question",
    placeholder="اكتب سؤالك هنا...",
    height=90,
    label_visibility="collapsed",
)

ask_clicked = st.button(
    "Ask →",
    disabled=(index is None or not query.strip()),
)

# ----------------------------
# RAG Pipeline
# ----------------------------
if ask_clicked and query.strip() and index is not None:

    # Retrieve relevant pages
    with st.spinner("Searching..."):
        results = retrieve(query, index, page_chunks, embed_model, k=10)

    # Generate answer
    with st.spinner("Generating answer..."):
        answer = generate_answer(query, results)

    # ----- Answer -----
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="label">Answer</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="answer-box">{answer}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        label="⬇ Download response.txt",
        data=answer.encode("utf-8"),
        file_name="response.txt",
        mime="text/plain",
    )

    # ----- Retrieved Pages -----
    st.markdown("<hr>", unsafe_allow_html=True)
    with st.expander(f"📄 Retrieved pages ({len(results)})", expanded=False):
        for r in results:
            st.markdown(
                f'<div class="chunk-card">'
                f'<div class="chunk-header">'
                f'<span>{r["label"]}</span>'
                f'<span>score: {r["score"]:.4f}</span>'
                f'</div>'
                f'{r["content"]}'
                f'</div>',
                unsafe_allow_html=True,
            )