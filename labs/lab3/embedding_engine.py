import os
import logging
import hashlib
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")
DEFAULT_COLLECTION = "news_articles"


class EmbeddingEngine:


    def __init__(
        self,
        persist_directory: str = DEFAULT_PERSIST_DIR,
        collection_name: str = DEFAULT_COLLECTION,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2", # The "v6" model
    ):
        """
        Parameters
        ----------
        persist_directory: directory where ChromaDB will persist data
        collection_name  : name of the Chroma collection to use
        embedding_model  : Local model name or path
        """
        print(f"[*] Initialising Local Embeddings using: {embedding_model}")
        
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'}, 
            encode_kwargs={'normalize_embeddings': True}
        )

        os.makedirs(persist_directory, exist_ok=True)

        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=persist_directory,
        )

        self._persist_directory = persist_directory
        self._collection_name = collection_name
        logger.info(
            "EmbeddingEngine initialised LOCAL (collection=%s, dir=%s)",
            collection_name,
            persist_directory,
        )

    def add_articles(self, articles: list[dict], topic: str = "") -> int:
        if not articles:
            return 0

        documents: list[Document] = []
        ids: list[str] = []

        existing_ids = self._get_existing_ids()

        for article in articles:
            doc_id = self._article_id(article)
            if doc_id in existing_ids:
                logger.debug("Skipping already-indexed article: %s", article.get("title"))
                continue

            text = self._article_text(article)
            if not text.strip():
                continue

            metadata = {
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "source": article.get("source", ""),
                "published_at": article.get("published_at", ""),
                "author": article.get("author", ""),
                "topic": topic,
            }

            documents.append(Document(page_content=text, metadata=metadata))
            ids.append(doc_id)

        if not documents:
            logger.info("No new articles to embed.")
            return 0

        self.vector_store.add_documents(documents=documents, ids=ids)
        logger.info("Added %d new article(s) to the vector store.", len(documents))
        return len(documents)

    def similarity_search(
        self, query: str, k: int = 5, topic_filter: Optional[str] = None
    ) -> list[Document]:
        where_filter = {"topic": topic_filter} if topic_filter else None

        if where_filter:
            results = self.vector_store.similarity_search(
                query, k=k, filter=where_filter
            )
        else:
            results = self.vector_store.similarity_search(query, k=k)

        logger.debug("similarity_search('%s') returned %d docs", query, len(results))
        return results

    def similarity_search_with_score(
        self, query: str, k: int = 5, topic_filter: Optional[str] = None
    ) -> list[tuple[Document, float]]:
        where_filter = {"topic": topic_filter} if topic_filter else None

        if where_filter:
            results = self.vector_store.similarity_search_with_score(
                query, k=k, filter=where_filter
            )
        else:
            results = self.vector_store.similarity_search_with_score(query, k=k)

        return results

    def get_collection_stats(self) -> dict:
        count = self.vector_store._collection.count()
        return {
            "collection": self._collection_name,
            "persist_directory": self._persist_directory,
            "document_count": count,
        }

    def clear_collection(self) -> None:
        self.vector_store._collection.delete(where={})
        logger.warning("Cleared all documents from collection '%s'.", self._collection_name)


    @staticmethod
    def _article_id(article: dict) -> str:
        key = article.get("url") or article.get("title") or str(article)
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    @staticmethod
    def _article_text(article: dict) -> str:
        parts = []
        if article.get("title"):
            parts.append(article["title"])
        if article.get("description"):
            parts.append(article["description"])
        if article.get("content"):
            parts.append(article["content"])
        return "\n\n".join(parts)

    def _get_existing_ids(self) -> set[str]:
        try:
            result = self.vector_store._collection.get(include=[])
            return set(result.get("ids", []))
        except Exception:
            return set()
