"""
Therapist Chatbot — Inference
Uses belal212/therapist-gemma-gguf_Q4_K_M (GGUF) + FAISS RAG from therapy books.

First time: the model is downloaded automatically from HuggingFace.
Make sure you ran rag_setup.py first to build the FAISS index.
"""

import os
import pickle
import numpy as np
import faiss
from pathlib import Path
from huggingface_hub import hf_hub_download
from llama_cpp import Llama
from sentence_transformers import SentenceTransformer

# ── Config ────────────────────────────────────────────────────────────────────
HF_REPO   = "belal212/therapist-gemma-gguf_Q4_K_M"
GGUF_FILE = "therapist-gemma-q4_K_M.gguf"
MODEL_DIR = Path(__file__).parent / "model"
INDEX_DIR = Path(__file__).parent / "faiss_index"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

TOP_K        = 5      # retrieved chunks per query
MAX_TOKENS   = 512    # max tokens to generate
CONTEXT_SIZE = 4096   # model context window
TEMPERATURE  = 0.7
# ──────────────────────────────────────────────────────────────────────────────


def download_model(repo: str, filename: str, save_dir: Path) -> str:
    save_dir.mkdir(parents=True, exist_ok=True)
    local_path = save_dir / filename
    if local_path.exists():
        print(f"[+] Model already cached at {local_path}")
        return str(local_path)
    print(f"[+] Downloading model from {repo} ...")
    path = hf_hub_download(repo_id=repo, filename=filename, local_dir=str(save_dir))
    print(f"[+] Model saved to {path}")
    return path


def load_rag(index_dir: Path):
    index_path = index_dir / "index.faiss"
    chunks_path = index_dir / "chunks.pkl"
    if not index_path.exists():
        print("[!] FAISS index not found. Run rag_setup.py first.")
        return None, None
    index = faiss.read_index(str(index_path))
    with open(chunks_path, "rb") as f:
        chunks = pickle.load(f)
    print(f"[+] Loaded FAISS index ({index.ntotal} vectors) and {len(chunks)} chunks.")
    return index, chunks


def retrieve(query: str, index, chunks: list, embed_model, top_k: int) -> list[str]:
    embedding = embed_model.encode([query], convert_to_numpy=True).astype(np.float32)
    faiss.normalize_L2(embedding)
    scores, indices = index.search(embedding, top_k)
    results = []
    for idx, score in zip(indices[0], scores[0]):
        if idx != -1 and score > 0.1:
            results.append(chunks[idx]["text"])
    return results


def build_prompt(user_message: str, context_chunks: list[str], history: list[dict]) -> str:
    # Build conversation history string
    history_str = ""
    for turn in history[-6:]:   # keep last 3 exchanges
        history_str += f"<start_of_turn>user\n{turn['user']}<end_of_turn>\n"
        history_str += f"<start_of_turn>model\n{turn['assistant']}<end_of_turn>\n"

    context_str = ""
    if context_chunks:
        context_str = "Relevant knowledge from therapy books:\n"
        for i, chunk in enumerate(context_chunks, 1):
            context_str += f"[{i}] {chunk}\n\n"

    system_prompt = (
        "You are a compassionate and professional therapist. "
        "You listen carefully, show empathy, and provide thoughtful, evidence-based responses. "
        "Use the provided therapy knowledge when relevant, but always respond in a warm, human way."
    )

    prompt = (
        f"<start_of_turn>system\n{system_prompt}\n\n{context_str}<end_of_turn>\n"
        f"{history_str}"
        f"<start_of_turn>user\n{user_message}<end_of_turn>\n"
        f"<start_of_turn>model\n"
    )
    return prompt


def chat_loop(llm: Llama, index, chunks, embed_model):
    print("\n" + "=" * 60)
    print("  Therapist AI — Type 'quit' or 'exit' to end the session")
    print("=" * 60 + "\n")

    history = []
    rag_available = index is not None

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Session ended]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            print("Therapist: Take care of yourself. Goodbye.")
            break

        # Retrieve relevant context
        context_chunks = []
        if rag_available:
            context_chunks = retrieve(user_input, index, chunks, embed_model, TOP_K)

        prompt = build_prompt(user_input, context_chunks, history)

        # Generate response
        response = llm(
            prompt,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            stop=["<end_of_turn>", "<start_of_turn>"],
            echo=False,
        )
        assistant_reply = response["choices"][0]["text"].strip()

        print(f"\nTherapist: {assistant_reply}\n")
        history.append({"user": user_input, "assistant": assistant_reply})


def main():
    print("=== Therapist AI ===")

    # 1. Download / locate model
    model_path = download_model(HF_REPO, GGUF_FILE, MODEL_DIR)

    # 2. Load FAISS index (optional — works without it)
    index, chunks = load_rag(INDEX_DIR)

    # 3. Load embedding model
    print(f"[+] Loading embedding model: {EMBED_MODEL_NAME}")
    embed_model = SentenceTransformer(EMBED_MODEL_NAME)

    # 4. Load LLM
    print(f"[+] Loading LLM (this may take a moment)...")
    llm = Llama(
        model_path=model_path,
        n_ctx=CONTEXT_SIZE,
        n_threads=os.cpu_count(),
        verbose=False,
    )

    # 5. Chat
    chat_loop(llm, index, chunks, embed_model)


if __name__ == "__main__":
    main()
