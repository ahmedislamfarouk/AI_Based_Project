"""Test the heuristic function standalone — no Docker dependencies needed.

Run: python tests/test_llm.py
"""

# Duplicate of CRISIS_WORDS + heuristic from core/model/inference.py
# so we can test without importing langchain/groq dependencies.

CRISIS_WORDS = ["kill myself", "want to die", "end my life", "suicide", "don't want to live",
                "hurt myself", "self-harm", "not worth living", "better off dead"]

def heuristic(face_emotion, voice_emotion, biometric, stt_text):
    combined = str(face_emotion) + str(voice_emotion) + str(stt_text)
    text = (stt_text or "").lower().strip()
    for w in CRISIS_WORDS:
        if w in text:
            return {"distress": 95, "response": "I'm really glad you told me. You don't have to go through this alone. Can you reach out to someone close to you right now?"}
    if "who are you" in text or text == "are you my therapist" or text.startswith("are you my"):
        return {"distress": 20, "response": "I'm a therapy support companion. I'm here to listen and help you work through things. What's on your mind?"}
    if "say hi" in text or "say hello" in text or "say hey" in text:
        for prefix in ["say hi to ", "say hi dr ", "say hi dr. ", "say hi ", "say hello to ", "say hello dr ", "say hello dr. ", "say hello "]:
            if prefix in text:
                name = text.split(prefix)[-1].strip().split(".")[0].strip().split(" ")[0]
                if name:
                    return {"distress": 20, "response": f"Hi {name.title()}! How are you doing today?"}
        return {"distress": 20, "response": "Hi there! How can I help you?"}
    if text in ("tell me a joke", "tell a joke", "a joke"):
        return {"distress": 20, "response": "Here's one: Why don't scientists trust atoms? Because they make up everything! 😊 So what's been on your mind?"}
    distress = 50
    if any(w in text or w in combined.lower() for w in ["kill", "die", "suicide", "hurt"]): distress = 95
    elif any(w in text or w in combined.lower() for w in ["angry", "rage", "furious", "hate"]): distress = 75
    elif any(w in text or w in combined.lower() for w in ["anxious", "panic", "worried", "fear", "scared", "overwhelmed"]): distress = 70
    elif any(w in text or w in combined.lower() for w in ["sad", "depressed", "crying", "lonely", "empty", "hopeless"]): distress = 65
    elif any(w in text or w in combined.lower() for w in ["tired", "exhausted", "burnout", "drained"]): distress = 55
    elif any(w in text or w in combined.lower() for w in ["happy", "calm", "grateful", "good", "great", "better"]): distress = 20
    if not text: return {"distress": distress, "response": "What's on your mind today?"}
    if any(w in text for w in CRISIS_WORDS): return {"distress": 95, "response": "I'm really glad you told me. You don't have to go through this alone. Can you reach out to someone close to you right now?"}
    if "cheat" in text or "betray" in text: return {"distress": 75, "response": "That's a deep kind of hurt. Want to talk about what happened?"}
    if "broke" in text or "money" in text or "fired" in text or "lost my job" in text: return {"distress": 60, "response": "That sounds really stressful. How are you coping with it?"}
    if "exhausted" in text or "burnout" in text or "tired" in text: return {"distress": 55, "response": "You sound drained. What's been the most demanding part lately?"}
    if "excited" in text or "awesome" in text or "proud" in text or "happy" in text: return {"distress": 20, "response": "That's wonderful! Tell me more about what's been going well."}
    if "?" in text or text.startswith("what") or text.startswith("why") or text.startswith("how"): return {"distress": distress, "response": "That's a good question. What do you think?"}
    if len(text) > 15: return {"distress": distress, "response": "That sounds like a lot. How does that feel for you?"}
    return {"distress": distress, "response": "Tell me more about that."}


def main():
    tests = [
        ("say hi to Mohammed", "Neutral", "Neutral", "Hi Mohammed"),
        ("say hi Dr. Laila", "Neutral", "Neutral", "Hi Laila"),
        ("say hi Dr Laila", "Neutral", "Neutral", "Hi Laila"),
        ("say hello to Ahmed", "Neutral", "Neutral", "Hi Ahmed"),
        ("say hi Sarah", "Neutral", "Neutral", "Hi Sarah"),
        ("Can you say hi Dr. Laila?", "Neutral", "Neutral", "Hi Laila"),
        ("say hello", "Neutral", "Neutral", "Hi there"),
        ("tell me a joke", "Neutral", "Neutral", "atom"),
        ("tell a joke", "Neutral", "Neutral", "atom"),
        ("who are you", "Neutral", "Neutral", "companion"),
        ("are you my therapist", "Neutral", "Neutral", "companion"),
        ("I want to kill myself", "Sad", "Neutral", "alone"),
        ("I'm very sad", "Sad", "Sad", "more"),
        ("My girlfriend cheated on me", "Sad", "Sad", "hurt"),
        ("I'm happy today!", "Happy", "Happy", "wonderful"),
        ("What is the meaning of life?", "Neutral", "Neutral", "question"),
        ("I'm exhausted", "Neutral", "Neutral", "drained"),
        ("", "Angry", "Neutral", "mind"),  # no speech, just emotion
    ]

    passed = 0
    failed = 0
    results = []
    print()
    print("=" * 70)
    print("  Heuristic Function Tests")
    print("=" * 70)
    print(f"  {'#':<3} {'Status':<8} {'Distress':<10} {'Input':<35} {'Response'}")
    print("  " + "-" * 65)
    for i, (stt, face, voice, expected) in enumerate(tests, 1):
        result = heuristic(face, voice, "N/A", stt)
        resp = result.get("response", "")
        dist = result.get("distress", 0)
        # Check if expected word is in response (or any of multiple expected words)
        if isinstance(expected, tuple):
            ok = any(e.lower() in resp.lower() for e in expected)
        else:
            ok = expected.lower() in resp.lower()
        status = "✓ PASS" if ok else "✗ FAIL"
        if ok: passed += 1
        else: failed += 1
        inp = stt[:32] + ".." if len(stt) > 34 else stt
        print(f"  {i:<3} {status:<8} {dist:<10} {inp:<35} '{resp[:50]}'")
        if not ok:
            results.append(f"  FAIL #{i}: '{stt}' → expected '{expected}' in response but got '{resp}'")

    print("  " + "-" * 65)
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 70)
    if failed:
        print("\n  Failures:")
        for r in results:
            print(r)
        print()
        return False
    
    print("\n  ✓ All tests passed! The heuristic is working correctly.")
    print()
    return True


if __name__ == "__main__":
    main()
