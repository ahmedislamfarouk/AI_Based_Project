import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyze_emails(prompt, email_content):
    """
    Sends the prompt and email history to Groq for analysis.
    """
    if not email_content:
        return "No email content found to analyze."

    prompt_template = f"""
I need you to analyze the following emails based on this request: "{prompt}"

Here are the emails:
{email_content}

Please provide a comprehensive analysis addressing the request.
"""
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # Using a powerful Groq model
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes email communications."},
                {"role": "user", "content": prompt_template}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error during Groq AI analysis: {str(e)}"
