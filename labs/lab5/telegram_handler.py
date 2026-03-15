import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# Import our custom services
from parser import parse_message
from email_service import fetch_emails, send_admin_report
from llm_service import analyze_emails

load_dotenv()

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def handle_workflow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Main logic when a message is received.
    """
    user_text = update.message.text
    chat_id = update.effective_chat.id
    
    await update.message.reply_text("Processing your request... 🔄")
    
    # 1. Parse
    prompt, emails = parse_message(user_text)
    
    if not emails:
        await update.message.reply_text("Please provide at least one email address.")
        return

    # 2. Fetch Emails
    all_email_content = ""
    for email in emails:
        logging.info(f"Fetching emails for {email}...")
        await update.message.reply_text(f"Fetching emails for {email}... 📧")
        content = fetch_emails(email)
        all_email_content += content + "\n"

    # 3. Analyze with LLM
    await update.message.reply_text("Analyzing emails with AI... 🤖")
    analysis = analyze_emails(prompt, all_email_content)

    # 4. Respond to Telegram
    # Split message if it's too long for Telegram (4096 chars)
    if len(analysis) > 4000:
        for i in range(0, len(analysis), 4000):
            await update.message.reply_text(analysis[i:i+4000])
    else:
        await update.message.reply_text(analysis)

    # 5. Send Admin Report
    send_admin_report(prompt, analysis)
    await update.message.reply_text("✅ Analysis complete. Admin report sent.")

def start_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return

    app = ApplicationBuilder().token(token).build()
    
    # Handle all text messages (that aren't commands)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_workflow))
    
    print("Bot is running...")
    app.run_polling()
