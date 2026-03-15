import re

def parse_message(text):
    """
    Parses the incoming Telegram message.
    Expected format:
    Line 1: Prompt
    Remaining lines: Email addresses
    """
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    if not lines:
        return None, []
    
    prompt = lines[0]
    emails = []
    
    # Simple regex to find email-like strings in the rest of the message
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    for line in lines[1:]:
        matches = re.findall(email_pattern, line)
        emails.extend(matches)
    
    # If no emails found by parsing lines, check the whole message for emails in brackets [] as suggested in the doc
    if not emails:
        emails = re.findall(email_pattern, text)
        # remove the prompt if it happened to be an email (unlikely but possible)
        if prompt in emails and len(emails) > 1:
            emails.remove(prompt)

    return prompt, list(set(emails))
