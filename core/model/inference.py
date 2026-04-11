import os
import time
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

class FusionAgent:
    def __init__(self, model="llama-3.3-70b-versatile"):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            print("Warning: GROQ_API_KEY not found in .env. Running mocked LLM mode.")
            self.llm = None
        else:
            self.llm = ChatGroq(api_key=self.api_key, model_name=model)
            
        self.system_prompt = """
        You are the 'Distress Monitor' for a Multimodal Emotion Monitoring System.
        You will receive multimodal inputs from:
        1. Voice Arousal Level
        2. Biometric Signals (Heart Rate, EDA)
        3. Video Emotion/State

        Your task:
        Determine the user's current 'Distress Level' (0-100) and provide a recommendation for an intervention or alert (e.g., 'Suggest deep breathing', 'Alert caregiver', 'Check connectivity', 'No action needed').
        Provide your output as a short one-liner in JSON format: {{"distress": level, "recommendation": "text"}}.
        """
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "Voice: {voice}, Biometric: {biometric}, Video: {video}")
        ])

    def fuse_inputs(self, voice, biometric, video):
        # Fallback to simple logic if LLM is unavailable
        if not self.llm:
            distress = 50 if "High" in voice or "Distressed" in video else 30
            return {"distress": distress, "recommendation": "No change (Mock Mode)"}

        try:
            chain = self.prompt | self.llm
            response = chain.invoke({
                "voice": voice,
                "biometric": biometric,
                "video": video
            })
            # Crude extraction of JSON if model returns text
            return response.content
        except Exception as e:
            # Fallback on API error
            return {"distress": 50, "recommendation": f"LLM Error: {str(e)}"}

if __name__ == "__main__":
    agent = FusionAgent()
    result = agent.fuse_inputs("High Arousal", "HR: 110, EDA: 300", "Bored/Not Present")
    print(f"Fusion Recommendation: {result}")
