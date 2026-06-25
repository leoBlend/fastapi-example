"""Backfill embeddings for todos that don't have one yet.

When you add embeddings to an existing table, the old rows have `embedding = NULL`
until you compute them. Run this once after migrating:

    python3 scripts/backfill_embeddings.py

It finds every todo with a NULL embedding, computes the vector, and saves it.
Safe to re-run — it only touches rows that are still missing a vector.
"""

import os
import sys

# Make the project root importable when running this file directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models import Todos
from embeddings import embed_text, todo_to_text


def backfill() -> int:
    db = SessionLocal()
    try:
        todos = db.query(Todos).filter(Todos.embedding.is_(None)).all()
        if not todos:
            print("No todos missing an embedding. Nothing to do.")
            return 0

        print(f"Embedding {len(todos)} todo(s)...")
        for todo in todos:
            todo.embedding = embed_text(todo_to_text(todo.title or "", todo.description or ""))
            print(f"  - todo {todo.id}: {todo.title!r}")
        db.commit()
        print(f"Done. Backfilled {len(todos)} todo(s).")
        return len(todos)
    finally:
        db.close()


if __name__ == "__main__":
    backfill()
