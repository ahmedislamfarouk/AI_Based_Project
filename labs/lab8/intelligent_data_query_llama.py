#!/usr/bin/env python3
"""
Application 1: Intelligent Data Query System (Text-to-SQL with Llama)

Features:
- LangChain-based natural language -> SQL generation
- Llama model integration (local GGUF via llama-cpp, or Groq API Llama)
- Schema-aware SQL generation
- SQL safety validation before execution
- Ambiguity detection and clarification loop
- Structured table-style output

Usage:
  python labs/lab8/intelligent_data_query_llama.py

Optional environment variables:
  MODEL_BACKEND=local|groq
  GROQ_API_KEY=...
  GROQ_MODEL=llama-3.1-8b-instant
  LOCAL_MODEL_PATH=/path/to/model.gguf
  AUTO_DOWNLOAD_MODEL=1
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import PromptTemplate


DB_PATH = Path(__file__).with_name("sample_store.db")
DEFAULT_LOCAL_REPO = "TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF"
DEFAULT_LOCAL_FILE = "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"


def setup_sample_database(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            city TEXT,
            email TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            price REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            order_item_id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        """
    )

    cur.execute("SELECT COUNT(*) FROM customers")
    if cur.fetchone()[0] == 0:
        cur.executescript(
            """
            INSERT INTO customers (name, city, email) VALUES
            ('Alice', 'Cairo', 'alice@example.com'),
            ('Bob', 'Alexandria', 'bob@example.com'),
            ('Charlie', 'Giza', 'charlie@example.com');

            INSERT INTO products (name, category, price) VALUES
            ('Laptop', 'Electronics', 1200.0),
            ('Headphones', 'Electronics', 150.0),
            ('Coffee Machine', 'Home', 220.0),
            ('Office Chair', 'Furniture', 310.0);

            INSERT INTO orders (customer_id, order_date, status) VALUES
            (1, '2026-04-10', 'Delivered'),
            (2, '2026-04-11', 'Shipped'),
            (1, '2026-04-12', 'Delivered'),
            (3, '2026-04-14', 'Processing');

            INSERT INTO order_items (order_id, product_id, quantity) VALUES
            (1, 1, 1),
            (1, 2, 2),
            (2, 2, 1),
            (2, 4, 1),
            (3, 3, 1),
            (4, 4, 2);
            """
        )

    conn.commit()
    conn.close()


def get_schema_description(conn: sqlite3.Connection) -> str:
    cur = conn.cursor()
    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()

    blocks: list[str] = []
    for (table_name,) in tables:
        columns = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
        fks = cur.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()

        col_lines = []
        for col in columns:
            _, name, col_type, not_null, _, pk = col
            flags = []
            if pk:
                flags.append("PK")
            if not_null:
                flags.append("NOT NULL")
            suffix = f" [{', '.join(flags)}]" if flags else ""
            col_lines.append(f"- {name}: {col_type}{suffix}")

        fk_lines = [
            f"- {table_name}.{fk[3]} -> {fk[2]}.{fk[4]}" for fk in fks
        ]

        section = [f"Table: {table_name}", "Columns:", *col_lines]
        if fk_lines:
            section.extend(["Relationships:", *fk_lines])
        blocks.append("\n".join(section))

    return "\n\n".join(blocks)


def build_llm():
    backend = os.getenv("MODEL_BACKEND", "local").strip().lower()

    if backend == "groq" or (backend != "local" and os.getenv("GROQ_API_KEY")):
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
            temperature=0,
        )

    model_path = os.getenv("LOCAL_MODEL_PATH", "").strip()
    if not model_path:
        model_path = str(Path(__file__).with_name(DEFAULT_LOCAL_FILE))

    model_file = Path(model_path)
    if not model_file.exists() and os.getenv("AUTO_DOWNLOAD_MODEL", "1") == "1":
        from huggingface_hub import hf_hub_download

        downloaded = hf_hub_download(
            repo_id=DEFAULT_LOCAL_REPO,
            filename=DEFAULT_LOCAL_FILE,
            local_dir=str(model_file.parent),
            local_dir_use_symlinks=False,
        )
        model_file = Path(downloaded)

    if not model_file.exists():
        raise FileNotFoundError(
            "No local GGUF model found. Set LOCAL_MODEL_PATH or enable AUTO_DOWNLOAD_MODEL=1."
        )

    from langchain_community.llms import LlamaCpp

    return LlamaCpp(
        model_path=str(model_file),
        temperature=0,
        max_tokens=128,
        top_p=0.95,
        n_ctx=2048,
        n_batch=64,
        n_threads=max(1, os.cpu_count() or 1),
        verbose=False,
    )


def extract_select_sql(text: str) -> str:
    if not text:
        return ""

    candidate = text.strip()

    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:sql)?", "", candidate).strip()
        candidate = re.sub(r"```$", "", candidate).strip()

    match = re.search(r"(?is)\bselect\b.+", candidate)
    if not match:
        return candidate

    sql_tail = match.group(0).strip()
    sql_tail = re.split(r"\n\s*\n", sql_tail, maxsplit=1)[0].strip()

    if ";" in sql_tail:
        sql_tail = sql_tail.split(";", 1)[0].strip()

    return sql_tail


def fast_path_sql(question: str) -> str | None:
    q = question.strip().lower()

    if any(phrase in q for phrase in ["show all tables", "show my tables", "list tables", "all my table", "all tables"]):
        return (
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )

    return None


def parse_json_like(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def validate_sql(sql: str) -> tuple[bool, str]:
    cleaned = sql.strip().rstrip(";")
    normalized = re.sub(r"\s+", " ", cleaned).strip().lower()

    if not normalized.startswith("select "):
        return False, "Only SELECT queries are allowed."

    dangerous = ["insert ", "update ", "delete ", "drop ", "alter ", "create ", "pragma ", "attach ", "detach "]
    if any(keyword in normalized for keyword in dangerous):
        return False, "Query contains potentially unsafe SQL keywords."

    if ";" in cleaned:
        return False, "Multiple SQL statements are not allowed."

    return True, cleaned


def format_rows(columns: list[str], rows: list[tuple[Any, ...]]) -> str:
    if not rows:
        return "No rows returned."

    widths = [len(col) for col in columns]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(str(value)))

    header = " | ".join(col.ljust(widths[i]) for i, col in enumerate(columns))
    sep = "-+-".join("-" * w for w in widths)
    body = [" | ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)) for row in rows]
    return "\n".join([header, sep, *body])


def main() -> None:
    setup_sample_database(DB_PATH)
    conn = sqlite3.connect(DB_PATH)

    schema = get_schema_description(conn)
    llm = build_llm()

    backend = os.getenv("MODEL_BACKEND", "local").strip().lower()
    use_ambiguity_check = os.getenv(
        "USE_AMBIGUITY_CHECK",
        "0" if backend == "local" else "1",
    ).strip().lower() in {"1", "true", "yes", "on"}

    ambiguity_prompt = ChatPromptTemplate.from_template(
        """
You are a data assistant. Determine if the user request is ambiguous for SQL generation.

Schema:
{schema}

User request:
{question}

Respond only as JSON with this shape:
{{
  "is_ambiguous": true or false,
  "clarification_question": "ask one short question if ambiguous, else empty string"
}}
""".strip()
    )

    sql_prompt = ChatPromptTemplate.from_template(
        """
You are a SQL expert. Generate one valid SQLite SELECT query only.
Rules:
- Use only tables/columns from schema
- Prefer explicit joins using relationships
- Return only SQL, no markdown, no explanation
- Never generate non-SELECT operations

Schema:
{schema}

User question:
{question}
""".strip()
    )

    local_sql_prompt = PromptTemplate.from_template(
        """
You are a SQLite query generator.
Output exactly one SQLite SELECT statement and nothing else.
No prose. No markdown. No backticks.

Schema:
{schema}

Question:
{question}

SQL:
""".strip()
    )

    ambiguity_chain = ambiguity_prompt | llm | StrOutputParser()
    sql_chain = sql_prompt | llm | StrOutputParser()
    local_sql_chain = local_sql_prompt | llm | StrOutputParser()

    print("Intelligent Data Query System (Llama + LangChain)")
    print(f"Database: {DB_PATH}")
    print("Type 'exit' to quit.\n")

    while True:
        question = input("Ask a question about the data: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue

        fast_sql = fast_path_sql(question)
        if fast_sql:
            raw_sql = fast_sql
        else:
            if use_ambiguity_check:
                ambiguity_raw = ambiguity_chain.invoke({"schema": schema, "question": question})
                ambiguity_data = parse_json_like(ambiguity_raw)

                is_ambiguous = bool(ambiguity_data.get("is_ambiguous", False))
                clarification = str(ambiguity_data.get("clarification_question", "")).strip()

                if is_ambiguous and clarification:
                    print(f"Clarification needed: {clarification}")
                    extra = input("Your clarification: ").strip()
                    if extra:
                        question = f"{question}\nAdditional clarification: {extra}"

            if backend == "local":
                raw_sql = local_sql_chain.invoke({"schema": schema, "question": question}).strip()
            else:
                raw_sql = sql_chain.invoke({"schema": schema, "question": question}).strip()

        raw_sql = extract_select_sql(raw_sql)
        safe, result = validate_sql(raw_sql)

        print("\nGenerated SQL:")
        print(raw_sql)

        if not safe:
            print(f"\nValidation failed: {result}\n")
            continue

        sql = result

        try:
            cur = conn.execute(sql)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
        except sqlite3.Error as e:
            print(f"\nExecution error: {e}\n")
            continue

        print("\nResult:")
        print(format_rows(columns, rows))
        print()

    conn.close()


if __name__ == "__main__":
    main()
