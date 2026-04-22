import os
import json
import time
import numpy as np

# ──────────────────────────────────────────────────────────────────────────────
# COMMENTED OUT: Groq API-based LLM (kept for easy switching back)
# ──────────────────────────────────────────────────────────────────────────────
# from langchain_groq import ChatGroq
# from langchain_core.prompts import ChatPromptTemplate
# from dotenv import load_dotenv
# load_dotenv()
#
# class FusionAgent:
#     def __init__(self, model="llama-3.3-70b-versatile"):
#         self.api_key = os.getenv("GROQ_API_KEY")
#         if not self.api_key:
#             print("Warning: GROQ_API_KEY not found in .env. Running mocked LLM mode.")
#             self.llm = None
#         else:
#             self.llm = ChatGroq(api_key=self.api_key, model_name=model)
#
#         self.system_prompt = """
# You are an AI Therapist in a Multimodal Emotion Monitoring System.
# You receive inputs from three sources:
# 1. Face Emotion Detection (FER) — the emotion detected from the user's facial expression.
# 2. Speech Emotion Recognition (SER) — the emotion detected from the user's voice tone.
# 3. Speech-to-Text (STT) — the actual words the user just spoke.
#
# Your task:
# - Analyze the user's emotional state holistically.
# - Respond as a caring therapist in FIRST PERSON (e.g., "I can see you're...", "I'm here with you...").
# - Provide a short, warm, conversational response (1-2 sentences max).
# - Also determine a Distress Level from 0-100.
#
# Output STRICTLY as JSON: {"distress": <0-100>, "response": "your therapist text here"}
# """
#         self.prompt = ChatPromptTemplate.from_messages([
#             ("system", self.system_prompt),
#             ("human", "Face emotion: {face_emotion}\nVoice emotion: {voice_emotion}\nBiometrics: {biometric}\nUser said: {stt_text}")
#         ])
#
#     def fuse_inputs(self, face_emotion, voice_emotion, biometric, stt_text=""):
#         if not self.llm:
#             distress = 50 if "High" in voice_emotion or "Distressed" in face_emotion else 30
#             return {"distress": distress, "response": "I'm here with you. How are you feeling?"}
#
#         try:
#             chain = self.prompt | self.llm
#             response = chain.invoke({
#                 "face_emotion": face_emotion,
#                 "voice_emotion": voice_emotion,
#                 "biometric": biometric,
#                 "stt_text": stt_text if stt_text else "(no speech detected)"
#             })
#             content = response.content
#             start = content.find("{")
#             end = content.rfind("}") + 1
#             if start >= 0 and end > start:
#                 parsed = json.loads(content[start:end])
#                 return {
#                     "distress": parsed.get("distress", 50),
#                     "response": parsed.get("response", "I'm here with you.")
#                 }
#             else:
#                 return {"distress": 50, "response": content}
#         except Exception as e:
#             print(f"[FusionAgent] LLM error: {e}")
#             return {"distress": 50, "response": f"I'm here with you. (Error: {str(e)})"}
#
# if __name__ == "__main__":
#     agent = FusionAgent()
#     result = agent.fuse_inputs("Happy", "Neutral", "HR: 75", "I feel good today")
#     print(f"Fusion Result: {result}")

# ──────────────────────────────────────────────────────────────────────────────
# NEW: Local fine-tuned therapist model + FAISS RAG
# ──────────────────────────────────────────────────────────────────────────────
from pathlib import Path
from llama_cpp import Llama
from sentence_transformers import SentenceTransformer
import faiss
import pickle

# Paths (Docker container paths)
MODEL_PATH = "/app/LLM/model/therapist-gemma-q4_K_M.gguf"
INDEX_DIR = "/app/LLM/faiss_index"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# Generation config
MAX_TOKENS = 512
CONTEXT_SIZE = 4096
TEMPERATURE = 0.7
TOP_K_RAG = 3


class FusionAgent:
    def __init__(self, model=None):
        """
        Uses local fine-tuned therapist Gemma GGUF + FAISS RAG.
        The 'model' arg is ignored (kept for backward compat with old API code).
        """
        self._llm = None
        self._index = None
        self._chunks = None
        self._embed_model = None
        self._rag_available = False

        self._load_local_model()
        self._load_rag()
        self._load_embed_model()

    def _load_local_model(self):
        if not os.path.exists(MODEL_PATH):
            print(f"[FusionAgent] Local model not found at {MODEL_PATH}. Will run in fallback mode.")
            return
        try:
            print("[FusionAgent] Loading local therapist model (this may take a moment)...")
            self._llm = Llama(
                model_path=MODEL_PATH,
                n_ctx=CONTEXT_SIZE,
                n_threads=os.cpu_count() or 4,
                n_gpu_layers=-1,   # offload all layers to GPU if llama-cpp compiled with CUDA
                verbose=False,
            )
            print("[FusionAgent] Local model loaded successfully.")
        except Exception as e:
            print(f"[FusionAgent] Failed to load local model: {e}")
            self._llm = None

    def _load_rag(self):
        index_path = os.path.join(INDEX_DIR, "index.faiss")
        chunks_path = os.path.join(INDEX_DIR, "chunks.pkl")
        if not os.path.exists(index_path):
            print(f"[FusionAgent] FAISS index not found at {index_path}. RAG disabled.")
            return
        try:
            self._index = faiss.read_index(index_path)
            with open(chunks_path, "rb") as f:
                self._chunks = pickle.load(f)
            print(f"[FusionAgent] FAISS RAG loaded: {self._index.ntotal} chunks.")
            self._rag_available = True
        except Exception as e:
            print(f"[FusionAgent] Failed to load RAG: {e}")
            self._index = None
            self._chunks = None

    def _load_embed_model(self):
        try:
            print(f"[FusionAgent] Loading embedding model: {EMBED_MODEL_NAME}")
            self._embed_model = SentenceTransformer(EMBED_MODEL_NAME)
            print("[FusionAgent] Embedding model ready.")
        except Exception as e:
            print(f"[FusionAgent] Failed to load embed model: {e}")
            self._embed_model = None

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

    def _build_prompt(self, face_emotion, voice_emotion, biometric, stt_text, context_chunks) -> str:
        system_prompt = (
            "You are a compassionate and professional AI therapist. "
            "You listen carefully, show empathy, and provide thoughtful, evidence-based responses. "
            "You have access to real-time multimodal inputs: face emotion, voice emotion, biometrics, and what the user just said. "
            "Respond as a warm, caring therapist in FIRST PERSON (e.g., 'I can see you're...', 'I'm here with you...'). "
            "Keep your response short (1-2 sentences). "
            "Also estimate a Distress Level from 0 to 100."
        )

        context_str = ""
        if context_chunks:
            context_str = "Relevant therapy knowledge:\n"
            for i, chunk in enumerate(context_chunks, 1):
                context_str += f"[{i}] {chunk}\n\n"

        user_message = (
            f"Face emotion: {face_emotion}\n"
            f"Voice emotion: {voice_emotion}\n"
            f"Biometrics: {biometric}\n"
            f"User said: {stt_text if stt_text else '(no speech detected)'}\n\n"
            f"Respond as a therapist and output STRICT JSON: {{\"distress\": <0-100>, \"response\": \"your therapist text here\"}}"
        )

        prompt = (
            f"<start_of_turn>system\n{system_prompt}\n\n{context_str}<end_of_turn>\n"
            f"<start_of_turn>user\n{user_message}<end_of_turn>\n"
            f"<start_of_turn>model\n"
        )
        return prompt

    def _parse_response(self, raw_text: str) -> dict:
        """Extract JSON from model output, with robust fallbacks."""
        raw_text = raw_text.strip()
        # Try to find JSON block
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw_text[start:end])
                return {
                    "distress": int(parsed.get("distress", 50)),
                    "response": parsed.get("response", "I'm here with you.").strip()
                }
            except Exception:
                pass
        # If no JSON found, just return the raw text as response with a heuristic distress
        distress = 50
        lower = raw_text.lower()
        if any(w in lower for w in ["sad", "angry", "fear", "distress", "worried", "anxious", "upset"]):
            distress = 70
        elif any(w in lower for w in ["happy", "good", "great", "calm", "relaxed", "positive"]):
            distress = 20
        return {"distress": distress, "response": raw_text}

    def fuse_inputs(self, face_emotion, voice_emotion, biometric, stt_text=""):
        # Fallback if local model not loaded
        if self._llm is None:
            distress = 50
            if any(x in str(face_emotion) + str(voice_emotion) for x in ["Angry", "Fear", "Sad", "High"]):
                distress = 70
            elif any(x in str(face_emotion) + str(voice_emotion) for x in ["Happy", "Calm", "Low"]):
                distress = 20
            return {"distress": distress, "response": "I'm here with you. How are you feeling right now?"}

        try:
            # Build query for RAG (combine all inputs)
            rag_query = f"{face_emotion} {voice_emotion} {stt_text}".strip()
            context_chunks = self._retrieve_context(rag_query) if rag_query else []

            prompt = self._build_prompt(face_emotion, voice_emotion, biometric, stt_text, context_chunks)

            response = self._llm(
                prompt,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                stop=["<end_of_turn>", "<start_of_turn>"],
                echo=False,
            )
            raw_text = response["choices"][0]["text"].strip()
            return self._parse_response(raw_text)
        except Exception as e:
            print(f"[FusionAgent] Local inference error: {e}")
            return {"distress": 50, "response": f"I'm here with you. (Error: {str(e)})"}


if __name__ == "__main__":
    agent = FusionAgent()
    result = agent.fuse_inputs("Happy", "Neutral", "HR: 75", "I feel good today")
    print(f"Fusion Result: {result}")
