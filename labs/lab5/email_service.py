import os
import smtplib
from email.message import EmailMessage
from imapclient import IMAPClient
import mailparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

def strip_html(html):
    """Strips HTML tags from email body."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator='\n')

def fetch_emails(email_address, limit=10):
    """
    Fetches the latest emails from a specific sender.
    Note: In a real scenario, you'd need the password for the sender's account,
    but here we assume we search within OUR own inbox for emails FROM that address.
    """
    host = os.getenv("EMAIL_HOST")
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    
    if not all([host, user, password]):
        return "Email credentials not configured."

    email_data = []
    try:
        with IMAPClient(host) as client:
            client.login(user, password)
            client.select_folder('INBOX')
            
            # Search for emails FROM the specified address
            messages = client.search(['FROM', email_address])
            
            # Get latest 'limit' messages
            messages = messages[-limit:]
            
            response = client.fetch(messages, ['RFC822'])
            
            for msgid, data in response.items():
                mail = mailparser.parse_from_bytes(data[b'RFC822'])
                body = mail.text_plain[0] if mail.text_plain else ""
                if not body and mail.text_html:
                    body = strip_html(mail.text_html[0])
                
                email_data.append({
                    "from": mail.from_[0][1] if mail.from_ else "Unknown",
                    "subject": mail.subject,
                    "date": str(mail.date),
                    "body": body[:500]  # Truncate long emails for LLM prompt
                })
        
        # Format for LLM
        formatted = ""
        for email in email_data:
            formatted += f"From: {email['from']}\nSubject: {email['subject']}\nDate: {email['date']}\nBody: {email['body']}\n---\n"
        return formatted
    except Exception as e:
        return f"Error fetching emails for {email_address}: {str(e)}"

def send_admin_report(prompt, analysis):
    """Sends the analysis to the administrator via SMTP."""
    smtp_host = os.getenv("SMTP_HOST")
    user = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")
    admin_email = os.getenv("ADMIN_EMAIL")
    
    if not all([smtp_host, user, password, admin_email]):
        return
    
    msg = EmailMessage()
    msg.set_content(f"Workflow Analysis Report\n\nOriginal Query: {prompt}\n\nLLM Response:\n{analysis}")
    msg['Subject'] = 'n8n Workflow Automation Report'
    msg['From'] = user
    msg['To'] = admin_email
    
    try:
        with smtplib.SMTP_SSL(smtp_host) as server:
            server.login(user, password)
            server.send_message(msg)
    except Exception as e:
        print(f"Error sending admin email: {e}")
