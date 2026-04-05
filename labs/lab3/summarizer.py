import os
import logging
from typing import Literal, Optional

from langchain_openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SummaryType = Literal["brief", "detailed"]


_BRIEF_SYSTEM = (
    "You are a professional news editor. "
    "Read the news article excerpts provided and write a concise summary of "
    "exactly 1-2 sentences that captures the most important information."
)
_BRIEF_HUMAN = "NEWS ARTICLE EXCERPTS:\n\n{text}\n\n1-2 SENTENCE SUMMARY:"

_MAP_SYSTEM = (
    "You are a news analyst. Summarise the following news article excerpt in "
    "2-3 sentences, preserving the key facts."
)
_MAP_HUMAN = "ARTICLE EXCERPT:\n\n{text}\n\nCONCISE SUMMARY:"

_REDUCE_SYSTEM = (
    "You are a professional news analyst. "
    "You will receive individual summaries of multiple related news articles. "
    "Write a single, cohesive paragraph (4-6 sentences) that synthesises all "
    "the information into one comprehensive news summary."
)
_REDUCE_HUMAN = "INDIVIDUAL SUMMARIES:\n\n{text}\n\nCOMPREHENSIVE PARAGRAPH SUMMARY:"


class NewsSummarizer:

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        model: str = "openai/gpt-4o-mini",
        temperature: float = 0.3,
    ):
        api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "An API key is required. Set OPENAI_API_KEY or pass "
                "openai_api_key= when instantiating NewsSummarizer."
            )

        # Configured for OpenRouter
        self._llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            openai_api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        parser = StrOutputParser()

        brief_prompt = ChatPromptTemplate.from_messages(
            [("system", _BRIEF_SYSTEM), ("human", _BRIEF_HUMAN)]
        )
        self._brief_chain = brief_prompt | self._llm | parser

        map_prompt = ChatPromptTemplate.from_messages(
            [("system", _MAP_SYSTEM), ("human", _MAP_HUMAN)]
        )
        self._map_chain = map_prompt | self._llm | parser

        reduce_prompt = ChatPromptTemplate.from_messages(
            [("system", _REDUCE_SYSTEM), ("human", _REDUCE_HUMAN)]
        )
        self._reduce_chain = reduce_prompt | self._llm | parser

        logger.info("NewsSummarizer initialised via OpenRouter (model=%s)", model)

    def summarize(
        self,
        articles: list[dict] | list[Document],
        summary_type: SummaryType = "brief",
        topic: str = "",
    ) -> str:
        """
        Summarise a list of articles.
        """
        if not articles:
            return "No articles available to summarise."

        docs = self._to_documents(articles)

        if len(docs) == 0:
            return "No readable content found in the provided articles."

        try:
            if summary_type == "brief":
                result = self._summarize_brief(docs)
            elif summary_type == "detailed":
                result = self._summarize_detailed(docs)
            else:
                raise ValueError(f"Unknown summary_type '{summary_type}'. Use 'brief' or 'detailed'.")
        except Exception as exc:
            logger.error("Summarisation failed: %s", exc)
            raise

        label = f" for topic '{topic}'" if topic else ""
        logger.info("Generated %s summary%s (%d docs)", summary_type, label, len(docs))
        return result.strip()

    def summarize_single(self, article: dict, summary_type: SummaryType = "brief") -> str:
        """Convenience wrapper to summarise a single article dict."""
        return self.summarize([article], summary_type=summary_type)

    def _summarize_brief(self, docs: list[Document]) -> str:
        # Stuff pattern: one prompt with all docs (capped at 10)
        combined = "\n\n---\n\n".join(d.page_content for d in docs[:10])
        return self._brief_chain.invoke({"text": combined})

    def _summarize_detailed(self, docs: list[Document]) -> str:
        # Map step – one call per doc
        mini_summaries = [
            self._map_chain.invoke({"text": doc.page_content}).strip()
            for doc in docs
        ]
        # Reduce step – combine all mini-summaries
        combined = "\n\n".join(
            f"[Article {i + 1}]: {s}" for i, s in enumerate(mini_summaries)
        )
        return self._reduce_chain.invoke({"text": combined})

    @staticmethod
    def _to_documents(articles: list) -> list[Document]:
        docs = []
        for item in articles:
            if isinstance(item, Document):
                docs.append(item)
            elif isinstance(item, dict):
                text_parts = []
                if item.get("title"):
                    text_parts.append(f"Title: {item['title']}")
                if item.get("description"):
                    text_parts.append(f"Description: {item['description']}")
                if item.get("content"):
                    text_parts.append(f"Content: {item['content']}")

                page_content = "\n".join(text_parts)
                if page_content.strip():
                    docs.append(
                        Document(
                            page_content=page_content,
                            metadata={
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "source": item.get("source", ""),
                                "published_at": item.get("published_at", ""),
                            },
                        )
                    )
        return docs
