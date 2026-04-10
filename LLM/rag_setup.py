"""
RAG Setup Script
Loads PDF books from ./books/, creates embeddings, and saves a FAISS index.
Run this once (or re-run when you add new books).
"""

import os
import pickle
import numpy as np
import faiss
from pathlib import Path
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

BOOKS_DIR = Path(__file__).parent / "books"
INDEX_DIR = Path(__file__).parent / "faiss_index"
CHUNK_SIZE = 512       # characters per chunk
CHUNK_OVERLAP = 64     # overlap between chunks
EMBED_MODEL = "all-MiniLM-L6-v2"


def load_pdfs(books_dir: Path) -> list[dict]:
    """Read all PDFs and return list of {text, source} dicts."""
    docs = []
    pdf_files = list(books_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"[!] No PDFs found in {books_dir}. Add therapy books there and re-run.")
        return docs

    for pdf_path in pdf_files:
        print(f"  Loading: {pdf_path.name}")
        reader = PdfReader(str(pdf_path))
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                docs.append({"text": text.strip(), "source": f"{pdf_path.name} (p.{page_num + 1})"})

    print(f"[+] Loaded {len(docs)} pages from {len(pdf_files)} PDF(s).")
    return docs


def chunk_documents(docs: list[dict], chunk_size: int, overlap: int) -> list[dict]:
    """Split page texts into smaller overlapping chunks."""
    chunks = []
    for doc in docs:
        text = doc["text"]
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({"text": chunk_text, "source": doc["source"]})
            start += chunk_size - overlap
    print(f"[+] Created {len(chunks)} chunks (size={chunk_size}, overlap={overlap}).")
    return chunks


def build_index(chunks: list[dict], embed_model_name: str, index_dir: Path):
    """Embed chunks and save FAISS index + metadata."""
    print(f"[+] Loading embedding model: {embed_model_name}")
    model = SentenceTransformer(embed_model_name)

    texts = [c["text"] for c in chunks]
    print(f"[+] Embedding {len(texts)} chunks...")
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype(np.float32)

    # Normalize for cosine similarity
    faiss.normalize_L2(embeddings)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # inner product on normalized = cosine
    index.add(embeddings)
    print(f"[+] FAISS index built: {index.ntotal} vectors, dim={dim}")

    index_dir.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_dir / "index.faiss"))
    with open(index_dir / "chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)

    print(f"[+] Saved index and chunks to {index_dir}/")


def main():
    print("=== RAG Setup ===")
    docs = load_pdfs(BOOKS_DIR)
    if not docs:
        return

    chunks = chunk_documents(docs, CHUNK_SIZE, CHUNK_OVERLAP)
    build_index(chunks, EMBED_MODEL, INDEX_DIR)
    print("\n[✓] Done. Run chat.py to start chatting.")


if __name__ == "__main__":
    main()
