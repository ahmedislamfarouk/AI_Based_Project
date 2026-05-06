import os
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
load_dotenv()
from langchain_groq import ChatGroq

MODEL_NAME = "llama-3.3-70b-versatile"
MAX_TOKENS = 300
TEMPERATURE = 0.6

# ── Crisis keywords ────────────────────────────────────
CRISIS_WORDS = ["kill myself", "want to die", "end my life", "suicide", "don't want to live",
                "hurt myself", "self-harm", "not worth living", "better off dead"]

THERAPIST_SYSTEM_PROMPT = (
    "You are a therapy companion.\n\n"
    "RULE 1 — Follow direct instructions FIRST, before anything else:\n"
    '  "say hi to X" or "say hi X" → just "Hi X!"\n'
    '  "tell me a joke" → tell a short joke\n'
    '  "who are you" → "I\'m here to listen."\n'
    "  If the user asks you to do something specific, JUST DO IT. No extra therapy.\n\n"
    "RULE 2 — If no instruction, respond therapeutically:\n"
    "  Validate feelings, explore gently, keep it to 1-2 sentences.\n"
    "  Never repeat what the user said back to them.\n"
    "  Never list emotions or data.\n\n"
    "RULE 3 — Crisis (suicide/harm): respond with care.\n\n"
    "Output JSON: {\"distress\": <0-100>, \"response\": \"...\"}"
)


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start:end])
            distress = int(parsed.get("distress", 50))
            distress = max(0, min(100, distress))
            response = parsed.get("response", "").strip()
            if response:
                return {"distress": distress, "response": response}
        except Exception:
            pass
    return None


def heuristic(face_emotion, voice_emotion, biometric, stt_text):
    combined = str(face_emotion) + str(voice_emotion) + str(stt_text)
    text = (stt_text or "").lower().strip()

    # ── Crisis detection ─────────────────────────────────
    for w in CRISIS_WORDS:
        if w in text:
            return {"distress": 95, "response": "I'm really glad you told me. You don't have to go through this alone. Can you reach out to someone close to you right now?"}

    # ── Direct questions ────────────────────────────────
    if "who are you" in text or text == "are you my therapist" or text.startswith("are you my"):
        return {"distress": 20, "response": "I'm a therapy support companion. I'm here to listen and help you work through things. What's on your mind?"}

    # Broad "say hi / say hello" detection: matches "say hi to X", "say hi X", "say hello Dr.", "say hi Dr. Laila"
    if "say hi" in text or "say hello" in text or "say hey" in text:
        for prefix in ["say hi to ", "say hi dr ", "say hi dr. ", "say hi ", "say hello to ", "say hello dr ", "say hello dr. ", "say hello "]:
            if prefix in text:
                name = text.split(prefix)[-1].strip().split(".")[0].strip().split(" ")[0]
                if name:
                    return {"distress": 20, "response": f"Hi {name.title()}! How are you doing today?"}
        return {"distress": 20, "response": "Hi there! How can I help you?"}
    if text in ("tell me a joke", "tell a joke"):
        return {"distress": 20, "response": "Here's one: Why don't scientists trust atoms? Because they make up everything! 😊 So what's been on your mind?"}

    # ── Distress assessment from emotion data ──────────
    distress = 50
    if any(w in text or w in combined.lower() for w in ["kill", "die", "suicide", "hurt"]):
        distress = 95
    elif any(w in text or w in combined.lower() for w in ["angry", "rage", "furious", "hate"]):
        distress = 75
    elif any(w in text or w in combined.lower() for w in ["anxious", "panic", "worried", "fear", "scared", "overwhelmed"]):
        distress = 70
    elif any(w in text or w in combined.lower() for w in ["sad", "depressed", "crying", "lonely", "empty", "hopeless"]):
        distress = 65
    elif any(w in text or w in combined.lower() for w in ["tired", "exhausted", "burnout", "drained"]):
        distress = 55
    elif any(w in text or w in combined.lower() for w in ["happy", "calm", "grateful", "good", "great", "better"]):
        distress = 20

    # ── Therapeutic responses ──────────────────────────
    if not text:
        return {"distress": distress, "response": "What's on your mind today?"}

    if any(w in text for w in CRISIS_WORDS):
        return {"distress": 95, "response": "I'm really glad you told me. You don't have to go through this alone. Can you reach out to someone close to you right now?"}

    if "cheat" in text or "betray" in text:
        return {"distress": 75, "response": "That's a deep kind of hurt. Want to talk about what happened?"}

    if "broke" in text or "money" in text or "fired" in text or "lost my job" in text:
        return {"distress": 60, "response": "That sounds really stressful. How are you coping with it?"}

    if "exhausted" in text or "burnout" in text or "tired" in text:
        return {"distress": 55, "response": "You sound drained. What's been the most demanding part lately?"}

    if "excited" in text or "awesome" in text or "proud" in text or "happy" in text:
        return {"distress": 20, "response": "That's wonderful! Tell me more about what's been going well."}

    if "?" in text or text.startswith("what") or text.startswith("why") or text.startswith("how"):
        return {"distress": distress, "response": "That's a good question. What do you think?"}

    if len(text) > 15:
        return {"distress": distress, "response": "That sounds like a lot. How does that feel for you?"}

    return {"distress": distress, "response": "Tell me more about that."}


class FusionAgent:
    def __init__(self, model=MODEL_NAME):
        self.api_key = os.environ.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
        self.llm = None

        if not self.api_key:
            print("[FusionAgent] No GROQ_API_KEY set. Running in heuristic-only mode.")
        else:
            try:
                self.llm = ChatGroq(api_key=self.api_key, model_name=model, max_tokens=MAX_TOKENS)
                print(f"[FusionAgent] Groq API ready ({model}).")
            except Exception as e:
                print(f"[FusionAgent] Groq init failed: {e}")
                self.llm = None

        self.system_prompt = THERAPIST_SYSTEM_PROMPT

    def fuse_inputs(self, face_emotion, voice_emotion, biometric, stt_text="", history=None):
        if not self.llm:
            return heuristic(face_emotion, voice_emotion, biometric, stt_text)

        history_block = ""
        if history:
            for h in history[-2:]:
                if h.get("user"):
                    history_block += f"User previously said: {h['user']}\n"
                if h.get("assistant"):
                    history_block += f"You replied: {h['assistant']}\n"

        user_msg = (
            f"Current context:\n"
            f"User just said: {stt_text or '(silent)'}\n"
            f"User's emotion (from face): {face_emotion}\n"
            f"User's emotion (from voice): {voice_emotion}\n"
        )
        if history_block:
            user_msg += f"Recent history:\n{history_block}\n"

        for attempt in range(2):
            try:
                response = self.llm.invoke([
                    ("system", self.system_prompt),
                    ("human", user_msg),
                ])
                parsed = _extract_json(response.content)
                if parsed:
                    return parsed
                print(f"[FusionAgent] Parse failed: {response.content[:200]}")
            except Exception as e:
                print(f"[FusionAgent] Attempt {attempt+1} failed: {e}")
                time.sleep(1)

        return heuristic(face_emotion, voice_emotion, biometric, stt_text)

    def fuse_inputs_fast(self, face_emotion, voice_emotion, biometric, stt_text="", history=None):
        return self.fuse_inputs(face_emotion, voice_emotion, biometric, stt_text, history)


class LocalFusionAgent:
    def __init__(self):
        import importlib.util
        spec = importlib.util.find_spec("llama_cpp")
        if spec is None:
            raise ImportError("llama-cpp-python not installed")

        from llama_cpp import Llama

        model_path = os.getenv("LLM_MODEL_PATH", "LLM/model/therapist-gemma-q4_K_M.gguf")
        gpu_devices = os.getenv("LLM_GPU_DEVICES", "0,1")
        threads = int(os.getenv("LLM_THREADS_PER_GPU", "5"))
        instance_count = len(gpu_devices.split(","))
        total_workers = instance_count * threads

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"GGUF model not found at {model_path}")

        import torch
        has_cuda = torch.cuda.is_available()
        n_gpu_layers = -1 if has_cuda else 0
        print(f"[LocalFusionAgent] Loading GGUF model (CUDA={'yes' if has_cuda else 'no'}, "
              f"n_gpu_layers={n_gpu_layers})...")
        self.model = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_gpu_layers=n_gpu_layers,
            n_threads=total_workers,
            verbose=False,
        )
        print(f"[LocalFusionAgent] Model ready ({total_workers} threads).")

        self.pool = ThreadPoolExecutor(max_workers=total_workers)
        self.system_prompt = THERAPIST_SYSTEM_PROMPT

    def _build_prompt(self, face_emotion, voice_emotion, biometric, stt_text, history=None):
        history_block = ""
        if history:
            for h in history[-2:]:
                if h.get("user"):
                    history_block += f"User previously said: {h['user']}\n"
                if h.get("assistant"):
                    history_block += f"You replied: {h['assistant']}\n"

        user_section = (
            f"Current context:\n"
            f"User just said: {stt_text or '(silent)'}\n"
            f"User's emotion (from face): {face_emotion}\n"
            f"User's emotion (from voice): {voice_emotion}\n"
        )
        if history_block:
            user_section += f"\nRecent history:\n{history_block}"

        return (
            f"<start_of_turn>system\n"
            f"{self.system_prompt}\n"
            f"<end_of_turn>\n"
            f"<start_of_turn>user\n"
            f"{user_section}\n"
            f"<end_of_turn>\n"
            f"<start_of_turn>model\n"
        )

    def _call(self, face_emotion, voice_emotion, biometric, stt_text, history=None):
        prompt = self._build_prompt(face_emotion, voice_emotion, biometric, stt_text, history)
        for attempt in range(2):
            try:
                resp = self.model(
                    prompt,
                    max_tokens=256,
                    temperature=TEMPERATURE,
                    stop=["<end_of_turn>"],
                    echo=False,
                )
                text = resp["choices"][0]["text"].strip()
                parsed = _extract_json(text)
                if parsed:
                    return parsed
                print(f"[LocalFusionAgent] Parse failed: {text[:100]}")
            except Exception as e:
                print(f"[LocalFusionAgent] Attempt {attempt+1} failed: {e}")
                time.sleep(0.5)
        return heuristic(face_emotion, voice_emotion, biometric, stt_text)

    def fuse_inputs(self, face_emotion, voice_emotion, biometric, stt_text="", history=None):
        future = self.pool.submit(self._call, face_emotion, voice_emotion, biometric, stt_text, history)
        return future.result()

    def fuse_inputs_fast(self, face_emotion, voice_emotion, biometric, stt_text="", history=None):
        return self.fuse_inputs(face_emotion, voice_emotion, biometric, stt_text, history)


if __name__ == "__main__":
    mode = os.getenv("LLM_MODE", "api")
    if mode == "local":
        agent = LocalFusionAgent()
    else:
        agent = FusionAgent()
    result = agent.fuse_inputs("Happy", "Neutral", "HR: 75", "I feel good today")
    print(f"Result: {result}")
