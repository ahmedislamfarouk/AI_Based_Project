import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"


class NewsRetriever:

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NEWS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "A NewsAPI key is required.  Set the NEWS_API_KEY environment "
                "variable or pass api_key= when instantiating NewsRetriever."
            )

    def fetch_articles(
        self,
        topic: str,
        max_articles: int = 10,
        days_back: int = 7,
        language: str = "en",
        sort_by: str = "relevancy",
    ) -> list[dict]:
        max_articles = min(max(1, max_articles), 100)
        from_date = (datetime.utcnow() - timedelta(days=days_back)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        params = {
            "q": topic,
            "from": from_date,
            "language": language,
            "sortBy": sort_by,
            "pageSize": max_articles,
            "apiKey": self.api_key,
        }

        try:
            response = requests.get(NEWSAPI_BASE_URL, params=params, timeout=15)
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            logger.error("NewsAPI HTTP error: %s", exc)
            raise
        except requests.exceptions.RequestException as exc:
            logger.error("Network error when calling NewsAPI: %s", exc)
            raise

        data = response.json()

        if data.get("status") != "ok":
            raise RuntimeError(
                f"NewsAPI returned an error: {data.get('message', 'unknown error')}"
            )

        articles = data.get("articles", [])
        logger.info("Fetched %d articles for topic '%s'", len(articles), topic)
        return [self._normalise(a) for a in articles]


    @staticmethod
    def _normalise(raw: dict) -> dict:
        """Convert a raw NewsAPI article dict into a clean, flat dict."""
        content = raw.get("content") or ""
        # NewsAPI truncates content at 200 chars with a trailing note; strip it
        if content and "[+" in content:
            content = content[: content.index("[+")].strip()

        return {
            "title": raw.get("title") or "",
            "description": raw.get("description") or "",
            "content": content,
            "url": raw.get("url") or "",
            "source": (raw.get("source") or {}).get("name") or "",
            "published_at": raw.get("publishedAt") or "",
            "author": raw.get("author") or "",
        }

    def get_article_text(self, article: dict) -> str:
        """
        Return the best available text for an article, preferring
        *content* → *description* → *title* in that order.
        """
        return article.get("content") or article.get("description") or article.get("title", "")
