# News Summarization Tool

A command-line application that retrieves news articles on any topic using
**NewsAPI**, vectorises them with **Local Embeddings**, stores them in
**ChromaDB**, and generates concise summaries through **LangChain** summarisation
chains.

---

## Project Structure

```
LAB3/
├── main.py               # CLI entry point
├── news_retriever.py     # NewsAPI integration
├── embedding_engine.py   # Embeddings + Chroma vector store
├── summarizer.py         # LangChain summarisation chains (brief & detailed)
├── user_manager.py       # User preference & history persistence (JSON)
├── requirements.txt      # Python dependencies
├── .env                  # API keys ( not committed)
└── README.md
```

---

## Requirements

| Tool | Version |
|------|---------|
| Python | ≥ 3.10 |
| pip | any recent version |

---

## Setup

### 1 — Clone / open the project

```bash
cd LAB3
```

### 2 — Create and activate a virtual environment *(recommended)*

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Obtain API keys

| Service | URL | Free tier |
|---------|-----|-----------|
| **OpenRouter** | https://openrouter.com
| **NewsAPI** | https://newsapi.org/register | 100 requests/day |

### 5 — Create a `.env` file


`.env` contents:

```dotenv
OPENAI_API_KEY=sk-...
NEWS_API_KEY=your_newsapi_key_here
```

> **Important:** Never commit `.env` to version control.

---

## Running the Application

```bash
python main.py
```

You will see an interactive menu:

```
============================================================
       NEWS SUMMARIZATION TOOL  (powered by LangChain)
============================================================

  Initialising components …
  Vector store ready (0 articles indexed).

  ┌─────────────────────────────────────────┐
  │  1.  Search news on a topic             │
  │  2.  Search a saved topic               │
  │  3.  Manage saved topics                │
  │  4.  View search history                │
  │  5.  Change preferences                 │
  │  6.  Exit                               │
  └─────────────────────────────────────────┘
  Select an option:
```

### Typical workflow

1. Press **1** and enter a topic (e.g. `artificial intelligence`).
2. Choose **brief** (1-2 sentence) or **detailed** (paragraph) summary.
3. The tool fetches articles, embeds them into ChromaDB, and prints the summary
   along with article sources.
4. Optionally save the topic for quick access via menu option **2**.

---

## Feature Overview

| Feature | Description |
|---------|-------------|
| **News retrieval** | `NewsRetriever` calls the NewsAPI `everything` endpoint and returns up to 100 articles per query. |
| **Embeddings** | `EmbeddingEngine` uses `sentence-transformers/all-MiniLM-L6-v2` to vectorise articles and stores them persistently in ChromaDB. Re-indexing the same URL is idempotent. |
| **Brief summary** | LangChain **stuff** chain — concatenates all article texts and asks GPT-4o-mini for a 1-2 sentence summary. |
| **Detailed summary** | LangChain **map-reduce** chain — each article is individually summarised (map), then all mini-summaries are combined into a coherent paragraph (reduce). |
| **User preferences** | Stored in `user_preferences.json`: saved topics, default summary type, max articles per query. |
| **Search history** | Every search is timestamped and persisted; viewable and clearable from the menu. |
| **Semantic search** | After indexing, ChromaDB is queried to retrieve the most semantically relevant documents for the summary. |

---

## Summarisation Chain Details

### Brief — Stuff Chain

```
All article texts  →  [Single GPT-4o-mini call]  →  1-2 sentence summary
```

Best for: quick headlines, topic overviews.

### Detailed — Map-Reduce Chain

```
Article 1  →  mini-summary₁  ┐
Article 2  →  mini-summary₂  ├──→  [Combine call]  →  Paragraph summary
Article N  →  mini-summaryₙ  ┘
```

Best for: deep-dives, research, understanding multiple perspectives.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for embeddings and chat completions |
| `NEWS_API_KEY` | Yes | NewsAPI key for article retrieval |
