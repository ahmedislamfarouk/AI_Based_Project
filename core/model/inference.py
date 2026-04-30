# -*- coding: utf-8 -*-
import os
import json
import time

# ──────────────────────────────────────────────────────────────────────────────
# Local fine-tuned therapist model + FAISS RAG  (PRIMARY)
# ──────────────────────────────────────────────────────────────────────────────
from pathlib import Path
from llama_cpp import Llama
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import pickle

# ──────────────────────────────────────────────────────────────────────────────
# OPTIONAL FALLBACK: Groq API-based LLM (fast, reliable)
# ──────────────────────────────────────────────────────────────────────────────
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
load_dotenv()

# Resolve model path — works both locally and inside Docker
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = str(_PROJECT_ROOT / "LLM" / "model" / "therapist-gemma-q4_K_M.gguf")
INDEX_DIR = str(_PROJECT_ROOT / "LLM" / "faiss_index")
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
MAX_TOKENS = 256
CONTEXT_SIZE = 4096
TEMPERATURE = 0.7
TOP_K_RAG = 2


def _detect_n_gpu_layers():
    try:
        import torch
        if torch.cuda.is_available():
            return -1
    except Exception:
        pass
    return 0


class FusionAgent:
    def __init__(self, model="llama-3.3-70b-versatile"):
        """
        PRIMARY: Local Gemma GGUF + FAISS RAG (default, no API needed).
        FALLBACK: Groq API (if LLM_MODE=api or local model fails).
        Set env LLM_MODE=api to force API mode.
        """
        self.mode = os.getenv("LLM_MODE", "local").strip().lower()
        self.api_key = os.environ.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
        self.llm = None          # Groq API handle
        self._local_llm = None   # Llama handle
        self._index = None
        self._chunks = None
        self._embed_model = None
        self._rag_available = False

        # ── 1. Try local model first (unless user explicitly wants api-only) ──
        if self.mode != "api":
            self._init_local()
            if self._local_llm:
                self._warmup_local_llm()
                print("[FusionAgent] Local LLM initialized (PRIMARY).")
            else:
                print("[FusionAgent] Local LLM failed to load.")

        # ── 2. Try Groq API (primary when LLM_MODE=api, or fallback otherwise) ──
        if self.mode == "api" or self._local_llm is None:
            if self.api_key:
                try:
                    self.llm = ChatGroq(api_key=self.api_key, model_name=model, max_tokens=512)
                    print("[FusionAgent] Groq API initialized (FALLBACK)." if self._local_llm else "[FusionAgent] Groq API initialized (PRIMARY).")
                except Exception as e:
                    print(f"[FusionAgent] Groq init failed: {e}")
                    self.llm = None
            else:
                if self._local_llm is None:
                    print("[FusionAgent] No GROQ_API_KEY found and local model unavailable.")

        self.system_prompt = (
            "You are a compassionate and professional AI therapist. "
            "You listen carefully, show empathy, and provide thoughtful, evidence-based responses. "
            "You have access to real-time multimodal inputs: face emotion, voice emotion, biometrics, and what the user just said. "
            "Respond as a warm, caring therapist in FIRST PERSON (e.g., 'I can see you're...', 'I'm here with you...'). "
            "Keep your response short (1-2 sentences). "
            "Also estimate a Distress Level from 0 to 100."
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "Face emotion: {face_emotion}\nVoice emotion: {voice_emotion}\nBiometrics: {biometric}\nUser said: {stt_text}\n\nOutput STRICT JSON: {{\"distress\": <0-100>, \"response\": \"your therapist text here\"}}")
        ])

    def _warmup_local_llm(self):
        """Run a single-token dummy inference to warm up CUDA kernels and VRAM."""
        if self._local_llm is None:
            return
        try:
            print("[FusionAgent] Warming up local LLM (first CUDA kernel compile)...")
            self._local_llm(
                "<start_of_turn>user\nHi<end_of_turn>\n<start_of_turn>model\n",
                max_tokens=1,
                temperature=0.0,
                stop=["<end_of_turn>"],
                echo=False,
            )
            print("[FusionAgent] Local LLM warmup complete.")
        except Exception as e:
            print(f"[FusionAgent] Warmup warning: {e}")

    def _init_local(self):
        if not os.path.exists(MODEL_PATH):
            print(f"[FusionAgent] Local model not found at {MODEL_PATH}.")
            return
        try:
            print("[FusionAgent] Loading local therapist model...")
            n_gpu = _detect_n_gpu_layers()
            self._local_llm = Llama(
                model_path=MODEL_PATH,
                n_ctx=CONTEXT_SIZE,
                n_threads=os.cpu_count() or 4,
                n_gpu_layers=n_gpu,
                verbose=False,
            )
            print(f"[FusionAgent] Local model loaded (gpu_layers={n_gpu}).")
        except Exception as e:
            print(f"[FusionAgent] Local model failed: {e}")
            self._local_llm = None
            return

        # Load RAG
        index_path = os.path.join(INDEX_DIR, "index.faiss")
        chunks_path = os.path.join(INDEX_DIR, "chunks.pkl")
        if os.path.exists(index_path):
            try:
                self._index = faiss.read_index(index_path)
                with open(chunks_path, "rb") as f:
                    self._chunks = pickle.load(f)
                print(f"[FusionAgent] FAISS RAG loaded: {self._index.ntotal} chunks.")
                self._rag_available = True
            except Exception as e:
                print(f"[FusionAgent] RAG failed: {e}")
        try:
            self._embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        except Exception as e:
            print(f"[FusionAgent] Embed model failed: {e}")

    def _retrieve_context(self, query: str) -> list[str]:
        if not self._rag_available or self._embed_model is None or self._index is None:
            return []
        try:
            embedding = self._embed_model.encode([query], convert_to_numpy=True).astype(np.float32)
            faiss.normalize_L2(embedding)
            scores, indices = self._index.search(embedding, TOP_K_RAG)
            results = []
            for idx, score in zip(indices[0], scores[0]):
                if idx != -1 and score > 0.1:
                    results.append(self._chunks[idx]["text"])
            return results
        except Exception as e:
            print(f"[FusionAgent] RAG retrieval error: {e}")
            return []

    def _build_local_prompt(self, face_emotion, voice_emotion, biometric, stt_text, context_chunks) -> str:
        system = (
            "You are a compassionate and professional AI therapist. "
            "Respond as a warm, caring therapist in FIRST PERSON. "
            "Keep your response short (1-2 sentences). "
            "Also estimate a Distress Level from 0 to 100."
        )
        ctx = ""
        if context_chunks:
            ctx = "Relevant therapy knowledge:\n" + "\n".join([f"[{i+1}] {c}" for i, c in enumerate(context_chunks)]) + "\n\n"
        user = (
            f"Face emotion: {face_emotion}\n"
            f"Voice emotion: {voice_emotion}\n"
            f"Biometrics: {biometric}\n"
            f"User said: {stt_text if stt_text else '(no speech detected)'}\n\n"
            f'Output STRICT JSON: {{"distress": <0-100>, "response": "your therapist text here"}}'
        )
        return f"<start_of_turn>system\n{system}\n\n{ctx}<end_of_turn>\n<start_of_turn>user\n{user}<end_of_turn>\n<start_of_turn>model\n"

    def _parse_json(self, content: str) -> dict:
        content = content.strip()
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(content[start:end])
                return {
                    "distress": int(parsed.get("distress", 50)),
                    "response": parsed.get("response", "I'm here with you.").strip()
                }
            except Exception:
                pass
        distress = 50
        lower = content.lower()
        if any(w in lower for w in ["sad", "angry", "fear", "distress", "worried", "anxious", "upset"]):
            distress = 70
        elif any(w in lower for w in ["happy", "good", "great", "calm", "relaxed", "positive"]):
            distress = 20
        return {"distress": distress, "response": content}

    def fuse_inputs(self, face_emotion, voice_emotion, biometric, stt_text=""):
        # ── PRIMARY: Local model ──
        if self._local_llm:
            try:
                rag_query = f"{face_emotion} {voice_emotion} {stt_text}".strip()
                context_chunks = self._retrieve_context(rag_query) if rag_query else []
                prompt = self._build_local_prompt(face_emotion, voice_emotion, biometric, stt_text, context_chunks)
                response = self._local_llm(
                    prompt,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    stop=["<end_of_turn>", "<start_of_turn>"],
                    echo=False,
                )
                raw_text = response["choices"][0]["text"].strip()
                return self._parse_json(raw_text)
            except Exception as e:
                print(f"[FusionAgent] Local inference error: {e}")
                # Fall through to API if available

        # ── FALLBACK: Groq API ──
        if self.llm:
            try:
                chain = self.prompt | self.llm
                response = chain.invoke({
                    "face_emotion": face_emotion,
                    "voice_emotion": voice_emotion,
                    "biometric": biometric,
                    "stt_text": stt_text if stt_text else "(no speech detected)"
                })
                return self._parse_json(response.content)
            except Exception as e:
                print(f"[FusionAgent] Groq error: {e}")

        # Ultimate fallback
        distress = 50
        if any(x in str(face_emotion) + str(voice_emotion) for x in ["Angry", "Fear", "Sad", "High"]):
            distress = 70
        elif any(x in str(face_emotion) + str(voice_emotion) for x in ["Happy", "Calm", "Low"]):
            distress = 20
        return {"distress": distress, "response": "I'm here with you. How are you feeling right now?"}

    def fuse_inputs_fast(self, face_emotion, voice_emotion, biometric, stt_text="", max_tokens=128):
        return self.fuse_inputs(face_emotion, voice_emotion, biometric, stt_text)


if __name__ == "__main__":
    agent = FusionAgent()
    result = agent.fuse_inputs("Happy", "Neutral", "HR: 75", "I feel good today")
    print(f"Fusion Result: {result}")
