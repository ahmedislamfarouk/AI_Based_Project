import os
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from langchain_core.documents import Document
from .vector_db import VectorDB

class KnowledgeRetriever:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NEWS_API_KEY")
        self.base_url = "https://newsapi.org/v2/everything"
        self.vector_db = VectorDB()

    def fetch_and_index_news(self, topic: str = "mental health", max_articles: int = 5):
        if not self.api_key:
            print("News API key missing. Skipping fetch.")
            return

        from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        params = {
            "q": topic,
            "from": from_date,
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": max_articles,
            "apiKey": self.api_key,
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            articles = data.get("articles", [])
            
            documents = []
            for article in articles:
                text = f"{article.get('title', '')}\n{article.get('description', '')}\n{article.get('content', '')}"
                metadata = {"source": article.get("source", {}).get("name"), "url": article.get("url")}
                documents.append(Document(page_content=text, metadata=metadata))
            
            if documents:
                self.vector_db.add_documents(documents)
                print(f"Indexed {len(documents)} articles for '{topic}'")
        except Exception as e:
            print(f"Fetch Error: {e}")

    def retrieve_context(self, query: str, k: int = 3) -> str:
        results = self.vector_db.search(query, k=k)
        return "\n---\n".join([res.page_content for res in results])
