import logging
import os
import sys
import textwrap

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Keep third-party libraries quiet
for _noisy in ("httpx", "urllib3", "chromadb", "openai", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)



def _hr(char: str = "─", width: int = 60) -> str:
    return char * width


def _wrap(text: str, indent: str = "  ") -> str:
    """Wrap long text to 80 chars with a hanging indent."""
    return textwrap.fill(text, width=80, initial_indent=indent, subsequent_indent=indent)


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def _check_env() -> bool:
    """Return True if all required environment variables are set."""
    missing = []
    for var in ("OPENAI_API_KEY", "NEWS_API_KEY"):
        if not os.getenv(var):
            missing.append(var)
    if missing:
        print(f"\n[ERROR] Missing environment variable(s): {', '.join(missing)}")
        print("  Create a .env file (see README.md) and add the missing keys.")
        return False
    return True


def action_search(retriever, engine, summarizer, user_manager) -> None:
    """Prompt for a topic, fetch articles, embed them, and display a summary."""
    print()
    topic = input("  Enter a topic to search for: ").strip()
    if not topic:
        print("  [!] No topic entered.")
        return

    # Pick summary type
    default_stype = user_manager.default_summary_type
    print(f"  Summary type — [b]rief / [d]etailed  (default: {default_stype}): ", end="")
    stype_input = input().strip().lower()
    if stype_input in ("d", "detailed"):
        summary_type = "detailed"
    elif stype_input in ("b", "brief"):
        summary_type = "brief"
    else:
        summary_type = default_stype

    max_articles = user_manager.max_articles
    print(f"\n  Fetching up to {max_articles} articles about '{topic}' …")

    try:
        articles = retriever.fetch_articles(topic, max_articles=max_articles)
    except Exception as exc:
        print(f"\n  [ERROR] Could not fetch articles: {exc}")
        return

    if not articles:
        print("  No articles found for that topic.")
        return

    print(f"  Retrieved {len(articles)} article(s).  Embedding …")

    try:
        added = engine.add_articles(articles, topic=topic)
        print(f"  {added} new article(s) added to the vector store.")
    except Exception as exc:
        print(f"\n  [WARN] Embedding failed ({exc}). Continuing with raw articles.")

    # Semantic search: retrieve most relevant docs for the topic query
    try:
        docs = engine.similarity_search(topic, k=min(len(articles), 8))
    except Exception:
        docs = articles  # fall back to raw articles

    print(f"\n  Generating {summary_type} summary …\n")
    print(_hr())

    try:
        summary = summarizer.summarize(docs if docs else articles, summary_type=summary_type, topic=topic)
        print(_bold(f"  {summary_type.upper()} SUMMARY — {topic.upper()}"))
        print(_hr("─", 60))
        print(_wrap(summary))
    except Exception as exc:
        print(f"  [ERROR] Summarisation failed: {exc}")
        return

    # Article list
    print(f"\n  {_bold('Sources:')}")
    for i, art in enumerate(articles[:max_articles], 1):
        print(f"    {i:>2}. {art.get('title', 'No title')}")
        if art.get("source"):
            print(f"        Source: {art['source']}  |  {art.get('published_at', '')[:10]}")
        if art.get("url"):
            print(f"        URL: {art['url']}")
    print(_hr())

    # Auto-save topic?
    if topic.lower() not in (t.lower() for t in user_manager.topics):
        save = input("\n  Save this topic for future searches? [y/N]: ").strip().lower()
        if save == "y":
            user_manager.add_topic(topic)
            print(f"  Topic '{topic}' saved.")

    # Record in history
    user_manager.record_search(
        topic=topic,
        summary_type=summary_type,
        article_count=len(articles),
    )


def action_manage_topics(user_manager) -> None:
    """View, add, and remove saved topics."""
    while True:
        topics = user_manager.topics
        print(f"\n  {_bold('Saved Topics')}  ({len(topics)})")
        if topics:
            for i, t in enumerate(topics, 1):
                print(f"    {i}. {t}")
        else:
            print("    (none)")

        print("\n  [a] Add topic   [r] Remove topic   [b] Back")
        choice = input("  > ").strip().lower()

        if choice == "a":
            new_topic = input("  Enter topic name: ").strip()
            if user_manager.add_topic(new_topic):
                print(f"  Added '{new_topic}'.")
            else:
                print(f"  Topic '{new_topic}' already saved or invalid.")

        elif choice == "r":
            if not topics:
                print("  No topics to remove.")
                continue
            idx_str = input("  Enter the number of the topic to remove: ").strip()
            try:
                idx = int(idx_str) - 1
                if 0 <= idx < len(topics):
                    removed = topics[idx]
                    user_manager.remove_topic(removed)
                    print(f"  Removed '{removed}'.")
                else:
                    print("  Invalid number.")
            except ValueError:
                print("  Please enter a valid number.")

        elif choice == "b":
            break
        else:
            print("  Unknown option.")


def action_view_history(user_manager) -> None:
    """Display recent search history."""
    history = user_manager.get_recent_history(n=20)
    print(f"\n  {_bold('Recent Search History')}  (newest first)")
    if not history:
        print("  (no searches recorded yet)")
    else:
        for i, entry in enumerate(history, 1):
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            print(
                f"    {i:>2}. [{ts}]  Topic: {entry.get('topic', '?')}"
                f"  |  Type: {entry.get('summary_type', '?')}"
                f"  |  Articles: {entry.get('article_count', '?')}"
            )

    print("\n  [c] Clear history   [b] Back")
    choice = input("  > ").strip().lower()
    if choice == "c":
        confirm = input("  Clear all history? [y/N]: ").strip().lower()
        if confirm == "y":
            user_manager.clear_history()
            print("  History cleared.")


def action_preferences(user_manager) -> None:
    """Change default summary type and article count."""
    prefs = user_manager.get_all_preferences()
    print(f"\n  {_bold('Current Preferences')}")
    print(f"    Default summary type : {prefs['default_summary_type']}")
    print(f"    Max articles per query: {prefs['max_articles']}")

    print("\n  [s] Change summary type   [n] Change max articles   [b] Back")
    choice = input("  > ").strip().lower()

    if choice == "s":
        print("  Choose: [b]rief or [d]etailed: ", end="")
        val = input().strip().lower()
        if val in ("b", "brief"):
            user_manager.default_summary_type = "brief"
            print("  Default summary type set to 'brief'.")
        elif val in ("d", "detailed"):
            user_manager.default_summary_type = "detailed"
            print("  Default summary type set to 'detailed'.")
        else:
            print("  Invalid choice.")

    elif choice == "n":
        val = input("  Enter max articles (1–100): ").strip()
        try:
            user_manager.max_articles = int(val)
            print(f"  Max articles set to {user_manager.max_articles}.")
        except ValueError:
            print("  Invalid number.")

    elif choice == "b":
        pass
    else:
        print("  Unknown option.")


def action_quick_topic_search(retriever, engine, summarizer, user_manager) -> None:
    """Search one of the user's saved topics quickly."""
    topics = user_manager.topics
    if not topics:
        print("  You have no saved topics.  Use the 'manage topics' menu to add some.")
        return

    print(f"\n  {_bold('Saved Topics')}")
    for i, t in enumerate(topics, 1):
        print(f"    {i}. {t}")
    print("  [b] Back")

    choice = input("\n  Enter topic number to search: ").strip().lower()
    if choice == "b":
        return
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(topics):
            # Temporarily monkeypatch the retriever call so we reuse action_search
            _orig_input = __builtins__.__dict__.get("input") if isinstance(__builtins__, dict) else getattr(__builtins__, "input", None)
            # Just delegate – cleaner to call directly
            print(f"\n  Searching for saved topic: '{topics[idx]}' …")
            # Set up mock interaction
            _run_saved_topic_search(
                topics[idx], retriever, engine, summarizer, user_manager
            )
        else:
            print("  Invalid number.")
    except ValueError:
        print("  Please enter a valid number.")


def _run_saved_topic_search(topic, retriever, engine, summarizer, user_manager) -> None:
    """Run a search for a saved topic using the default summary type."""
    summary_type = user_manager.default_summary_type
    max_articles = user_manager.max_articles

    print(f"\n  Fetching up to {max_articles} articles about '{topic}' …")
    try:
        articles = retriever.fetch_articles(topic, max_articles=max_articles)
    except Exception as exc:
        print(f"\n  [ERROR] Could not fetch articles: {exc}")
        return

    if not articles:
        print("  No articles found.")
        return

    print(f"  Retrieved {len(articles)} article(s).  Embedding …")
    try:
        engine.add_articles(articles, topic=topic)
    except Exception as exc:
        print(f"  [WARN] Embedding failed ({exc}).")

    try:
        docs = engine.similarity_search(topic, k=min(len(articles), 8))
    except Exception:
        docs = articles

    print(f"\n  Generating {summary_type} summary …\n")
    print(_hr())
    try:
        summary = summarizer.summarize(docs if docs else articles, summary_type=summary_type, topic=topic)
        print(_bold(f"  {summary_type.upper()} SUMMARY — {topic.upper()}"))
        print(_hr("─", 60))
        print(_wrap(summary))
    except Exception as exc:
        print(f"  [ERROR] Summarisation failed: {exc}")
        return

    print(f"\n  {_bold('Sources:')}")
    for i, art in enumerate(articles, 1):
        print(f"    {i:>2}. {art.get('title', 'No title')}")
        if art.get("url"):
            print(f"        URL: {art['url']}")
    print(_hr())

    user_manager.record_search(
        topic=topic,
        summary_type=summary_type,
        article_count=len(articles),
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n" + "=" * 60)
    print("       NEWS SUMMARIZATION TOOL  (powered by LangChain)")
    print("=" * 60)

    if not _check_env():
        sys.exit(1)

    # Lazy imports so missing packages give a clear message
    try:
        from news_retriever import NewsRetriever
        from embedding_engine import EmbeddingEngine
        from summarizer import NewsSummarizer
        from user_manager import UserManager
    except ImportError as exc:
        print(f"\n[ERROR] Could not import a required module: {exc}")
        print("  Run:  pip install -r requirements.txt")
        sys.exit(1)

    print("\n  Initialising components …")
    try:
        user_manager = UserManager()
        retriever = NewsRetriever()
        engine = EmbeddingEngine()
        summarizer = NewsSummarizer()
    except Exception as exc:
        print(f"\n[ERROR] Initialisation failed: {exc}")
        sys.exit(1)

    stats = engine.get_collection_stats()
    print(f"  Vector store ready ({stats['document_count']} articles indexed).")
    saved_topics = user_manager.topics
    if saved_topics:
        print(f"  Saved topics: {', '.join(saved_topics)}")

    MENU = """
  ┌─────────────────────────────────────────┐
  │  1.  Search news on a topic             │
  │  2.  Search a saved topic               │
  │  3.  Manage saved topics                │
  │  4.  View search history                │
  │  5.  Change preferences                 │
  │  6.  Exit                               │
  └─────────────────────────────────────────┘"""

    while True:
        print(MENU)
        choice = input("  Select an option: ").strip()

        if choice == "1":
            action_search(retriever, engine, summarizer, user_manager)
        elif choice == "2":
            action_quick_topic_search(retriever, engine, summarizer, user_manager)
        elif choice == "3":
            action_manage_topics(user_manager)
        elif choice == "4":
            action_view_history(user_manager)
        elif choice == "5":
            action_preferences(user_manager)
        elif choice in ("6", "q", "quit", "exit"):
            print("\n  Goodbye!\n")
            break
        else:
            print("  Unknown option.  Enter a number from 1 to 6.")


if __name__ == "__main__":
    main()
