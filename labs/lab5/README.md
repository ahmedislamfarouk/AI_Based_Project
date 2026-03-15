# Lab 5: n8n Workflow Automation (Python Implementation)

## 📋 Project Overview
This project automates the process of fetching, analyzing, and reporting email communications. It mimics a complex **n8n workflow** but is implemented in **Python** for maximum control and efficiency.

### How it works:
1. **Trigger**: You send a message to a **Telegram Bot**.
2. **Retrieve**: The bot reads your prompt and target email addresses.
3. **Analyze**: It fetches the last 10 emails from those addresses via **IMAP** and sends them to **Groq (Llama-3)** for analysis.
4. **Respond**: You get the AI summary back on Telegram, and a professional report is emailed to the **Admin**.

---

## 🔗 Where does n8n fit in?
This project is a **Python version of an n8n workflow**. In n8n, you would connect "nodes" with lines to move data. Here, we use modular Python files to act as those nodes:

| n8n Node | Python File | Description |
| :--- | :--- | :--- |
| **Telegram Trigger** | `telegram_handler.py` | Listens for new messages. |
| **Function (Parsing)** | `parser.py` | Extracts the prompt and emails from your text. |
| **Email (IMAP)** | `email_service.py` | Connects to your inbox to read emails. |
| **Groq/AI Node** | `llm_service.py` | Sends the data to the AI for analysis. |
| **Email (SMTP)** | `email_service.py` | Sends the final report to the administrator. |
| **Workflow Root** | `main.py` | The "Start" button that runs the whole automation. |

---

## 🛠️ File Breakdown
*   **`main.py`**: The entry point. Starts the bot loop.
*   **`telegram_handler.py`**: Handles user interaction (Send/Receive messages).
*   **`email_service.py`**: The "Post Office" of the project—handles both reading and sending mail.
*   **`llm_service.py`**: The "Brain"—connects to Groq for analysis.
*   **`parser.py`**: The "Secretary"—cleans and prepares the data.
*   **`.env`**: The "Vault"—stores your API keys and passwords safely.

---

## 🚀 Setup
1. Fill in your keys in `.env`.
2. Run `pip install -r requirements.txt`.
3. Run `python main.py`.
