"""
RAG Engine - Backend logic for embedding, indexing, retrieval, and generation.
Handles: page-based chunking, FAISS vector index, SentenceTransformer embeddings, Gemini generation.
"""

import re
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import streamlit as st

# ----------------------------
# Static API Key
# ----------------------------
GEMINI_API_KEY = "//"


# ----------------------------
# Load Embedding Model (cached)
# ----------------------------
@st.cache_resource(show_spinner=False)
def load_embed_model():
    """Load and cache the SentenceTransformer embedding model."""
    return SentenceTransformer("BAAI/bge-base-en-v1.5")


# ----------------------------
# Page-Based Chunking
# ----------------------------
def chunk_by_pages(text: str) -> list[dict]:
    """
    Split text into chunks using page markers of the form:
        === صفحة المقدمة ===
        === صفحة 1 ===
        === صفحة 2 ===  ... etc.

    Each chunk keeps the page label so it can be shown in the UI.

    Args:
        text: Full document text containing page markers.

    Returns:
        List of dicts with keys:
            - 'label'   : page header string (e.g. "صفحة 1")
            - 'content' : text body of that page (stripped)
    """
    # Match any line that looks like  === ... ===
    pattern = r"(===\s*.+?\s*===)"
    parts = re.split(pattern, text)

    chunks = []
    current_label = "غير محدد"  # fallback label for content before the first marker

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check if this part is a page-marker header
        if re.fullmatch(r"===\s*.+?\s*===", part):
            # Extract the label text between the === delimiters
            current_label = part.strip("= ").strip()
        else:
            # This is the body text that belongs to the current label
            if part:
                chunks.append({"label": current_label, "content": part})

    return chunks


# ----------------------------
# Build FAISS Index
# ----------------------------
@st.cache_resource(show_spinner=False)
def build_index(file_content: str):
    """
    Chunk text by pages, encode embeddings, and build a FAISS inner-product index.

    Args:
        file_content: Raw text content of the uploaded document.

    Returns:
        Tuple of (faiss_index, page_chunks, embed_model).
        page_chunks is a list of dicts: [{'label': ..., 'content': ...}, ...]
    """
    embed_model = load_embed_model()

    # Split document into page-level chunks
    page_chunks = chunk_by_pages(file_content)

    if not page_chunks:
        raise ValueError("No page markers found. Make sure the file contains === صفحة X === markers.")

    # Encode chunk content with passage prefix required by BGE model
    passages = [f"passage: {c['content']}" for c in page_chunks]
    embeddings = embed_model.encode(passages, normalize_embeddings=True)
    embeddings = np.array(embeddings).astype("float32")

    # Build cosine-similarity index (inner product on normalized vectors)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    return index, page_chunks, embed_model


# ----------------------------
# Retrieval
# ----------------------------
def retrieve(query: str, index, page_chunks: list[dict], embed_model, k: int = 15) -> list[dict]:
    """
    Retrieve the top-k most relevant page chunks for a query.

    Args:
        query: User's question string.
        index: FAISS index containing page embeddings.
        page_chunks: List of dicts with 'label' and 'content' keys.
        embed_model: Loaded SentenceTransformer model.
        k: Number of pages to retrieve.

    Returns:
        List of dicts, each with 'label', 'content', and 'score' keys.
    """
    # Cap k to available pages
    k = min(k, len(page_chunks))

    # Encode query with query prefix required by BGE model
    query_embedding = embed_model.encode(
        [f"query: {query}"],
        normalize_embeddings=True
    )
    query_embedding = np.array(query_embedding).astype("float32")

    scores, indices = index.search(query_embedding, k)

    results = []
    for idx, score in zip(indices[0], scores[0]):
        chunk = page_chunks[idx].copy()
        chunk["score"] = float(score)
        results.append(chunk)

    return results


# ----------------------------
# Gemini Answer Generation
# ----------------------------
def generate_answer(query: str, retrieved_chunks: list[dict]) -> str:
    """
    Generate a grounded answer using Gemini based on retrieved page context.

    Args:
        query: User's original question.
        retrieved_chunks: List of dicts with 'label' and 'content' keys.

    Returns:
        Generated answer string from Gemini.
    """
    genai.configure(api_key=GEMINI_API_KEY)

    # Build context with page labels so Gemini can reference them
    context_parts = [f"[{c['label']}]\n{c['content']}" for c in retrieved_chunks]
    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""
أجب على السؤال باستخدام السياق التالي فقط.
يمكنك الإشارة إلى أرقام الصفحات عند الحاجة.

السياق:
{context}

السؤال:
{query}
"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text
