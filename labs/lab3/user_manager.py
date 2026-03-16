import json
import logging
import os
from datetime import datetime, timezone
from typing import Literal, Optional

logger = logging.getLogger(__name__)

SummaryType = Literal["brief", "detailed"]
DEFAULT_PREFS_FILE = os.path.join(os.path.dirname(__file__), "user_preferences.json")

_DEFAULT_PREFS: dict = {
    "topics": [],
    "default_summary_type": "brief",
    "max_articles": 10,
    "history": [],
}


class UserManager:

    def __init__(self, prefs_file: str = DEFAULT_PREFS_FILE):
        self._prefs_file = prefs_file
        self._data = self._load()
        
    @property
    def topics(self) -> list[str]:
        """Return the list of saved topics."""
        return list(self._data.get("topics", []))

    def add_topic(self, topic: str) -> bool:
        """
        Save *topic* to the user's interest list.

        Returns ``True`` if the topic was added, ``False`` if already present.
        """
        topic = topic.strip()
        if not topic:
            return False
        if topic.lower() in (t.lower() for t in self._data["topics"]):
            return False
        self._data["topics"].append(topic)
        self._save()
        logger.info("Topic added: %s", topic)
        return True

    def remove_topic(self, topic: str) -> bool:
        """
        Remove *topic* from the saved list.

        Returns ``True`` if removed, ``False`` if it was not in the list.
        """
        before = len(self._data["topics"])
        self._data["topics"] = [
            t for t in self._data["topics"] if t.lower() != topic.strip().lower()
        ]
        if len(self._data["topics"]) < before:
            self._save()
            logger.info("Topic removed: %s", topic)
            return True
        return False

    @property
    def default_summary_type(self) -> SummaryType:
        return self._data.get("default_summary_type", "brief")  # type: ignore[return-value]

    @default_summary_type.setter
    def default_summary_type(self, value: SummaryType) -> None:
        if value not in ("brief", "detailed"):
            raise ValueError("summary_type must be 'brief' or 'detailed'.")
        self._data["default_summary_type"] = value
        self._save()

    @property
    def max_articles(self) -> int:
        return int(self._data.get("max_articles", 10))

    @max_articles.setter
    def max_articles(self, value: int) -> None:
        value = max(1, min(100, int(value)))
        self._data["max_articles"] = value
        self._save()


    @property
    def history(self) -> list[dict]:
        """Return a copy of the search history (most recent last)."""
        return list(self._data.get("history", []))

    def record_search(
        self,
        topic: str,
        summary_type: SummaryType,
        article_count: int,
    ) -> None:
        """Append an entry to the search history and persist."""
        entry = {
            "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "topic": topic,
            "summary_type": summary_type,
            "article_count": article_count,
        }
        self._data.setdefault("history", []).append(entry)
        self._save()
        logger.debug("Recorded search: %s", entry)

    def clear_history(self) -> None:
        """Delete all search history."""
        self._data["history"] = []
        self._save()
        logger.info("Search history cleared.")

    def get_recent_history(self, n: int = 10) -> list[dict]:
        """Return the *n* most recent history entries (newest first)."""
        return list(reversed(self._data.get("history", [])))[:n]

    def get_all_preferences(self) -> dict:
        """Return a copy of all stored preferences (excluding history)."""
        return {
            "topics": self.topics,
            "default_summary_type": self.default_summary_type,
            "max_articles": self.max_articles,
        }

    def reset_to_defaults(self) -> None:
        """Reset all preferences (including history) to factory defaults."""
        self._data = dict(_DEFAULT_PREFS)
        self._data["topics"] = []
        self._data["history"] = []
        self._save()
        logger.warning("User preferences reset to defaults.")

    def _load(self) -> dict:
        if os.path.exists(self._prefs_file):
            try:
                with open(self._prefs_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                # Back-fill any missing keys from the defaults
                for key, default in _DEFAULT_PREFS.items():
                    data.setdefault(key, default)
                logger.debug("Loaded preferences from %s", self._prefs_file)
                return data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Could not read preferences file (%s) – using defaults.", exc
                )

        return dict(_DEFAULT_PREFS)

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._prefs_file) or ".", exist_ok=True)
            with open(self._prefs_file, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error("Failed to save preferences: %s", exc)
