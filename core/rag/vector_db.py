import os
import hashlib
from typing import Optional, List, Tuple
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

class VectorDB:
    def __init__(
        self,
        persist_directory: str = "data/processed/chroma_db",
        collection_name: str = "emotion_knowledge",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
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

    def add_documents(self, documents: List[Document]):
        ids = [hashlib.sha256(doc.page_content.encode()).hexdigest()[:32] for doc in documents]
        self.vector_store.add_documents(documents=documents, ids=ids)

    def search(self, query: str, k: int = 3) -> List[Document]:
        return self.vector_store.similarity_search(query, k=k)

    def search_with_score(self, query: str, k: int = 3) -> List[Tuple[Document, float]]:
        return self.vector_store.similarity_search_with_score(query, k=k)
