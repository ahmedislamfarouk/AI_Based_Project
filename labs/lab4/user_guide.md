# User Guide: Lab 4 LangChain Applications

## Overview
This laboratory contains two functional LangChain applications:
1. **Enterprise Customer Support System**: A RAG-based agent for product support.
2. **Academic Research Assistant**: A synthesis engine for research papers and Wikipedia data.

---

## Setup Instructions

1. **Install Dependencies**:
   ```bash
   pip install langchain langchain-openai langchain-community chromadb faiss-cpu sentence-transformers wikipedia arxiv
   ```

2. **Set Environment Variables**:
   You must have an OpenAI API Key.
   ```bash
   export OPENAI_API_KEY='your-key-here'
   ```

---

## Application 1: Customer Support System
**File:** `app1_customer_support.py`

### Feature Highlights:
- **Knowledge Bases**: Covers "Product A", "Product B", and "Returns Policy".
- **Specialized Tools**:
  - `OrderTracker`: Mock tracker for simulated orders.
  - `StockChecker`: Real-time stock availability simulation.
- **Memory**: Remembers previous questions in the session.

### Example Usage:
```python
support = CustomerSupportSystem("./knowledge")
result = support.process_query("What is the battery life of the student laptop?")
# The system will search 'product_b.txt', find the 15-hour spec, and reply.
```

---

## Application 2: Academic Research Assistant
**File:** `app2_research_assistant.py`

### Feature Highlights:
- **Multi-Source Fetching**: Combines high-level Wikipedia overviews with technical ArXiv paper abstracts.
- **Synthesis Engine**: Uses GPT-4 to convert messy data into a structured PhD-level report.
- **Source Management**: Automatically handles citations for every paper retrieved.

### Example Usage:
```python
assistant = AcademicResearchAssistant()
report = assistant.generate_research_report("Sustainability in Neural Network Training")
# Check 'research_report.md' for the output.
```

---

## Error Handling
Both applications include `try-except` blocks and input filtering to handle API failures or irrelevant queries gracefully.
