"""The 'generation' half of RAG: turn retrieved todos into a grounded answer.

Retrieval (vector search) happens in routers/rag.py. This module takes the todos
that search found and asks Claude to answer the user's question *using only those
todos*. That grounding instruction is what makes this RAG rather than the model
answering from general knowledge — Claude can only talk about todos we retrieved,
so it can't invent ones that don't exist.
"""

import os

from anthropic import Anthropic

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = (
    "You are a helpful assistant inside a personal todo app. Answer the user's "
    "question using ONLY the todos provided in the context below. These are the "
    "user's own todos, retrieved by semantic search. If the todos don't contain "
    "enough information to answer, say so plainly — never invent a todo that "
    "isn't listed. Be concise and refer to todos by their title."
)

# Created lazily so importing this module (e.g. in tests) doesn't require an API
# key. The key is read from ANTHROPIC_API_KEY in the environment / .env.
_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def format_todos(todos) -> str:
    """Render retrieved todos into a plain-text context block for the prompt."""
    if not todos:
        return "(no matching todos)"
    lines = []
    for t in todos:
        done = "done" if t.complete else "open"
        lines.append(
            f"- [{done}] (priority {t.priority}) {t.title}: {t.description}"
        )
    return "\n".join(lines)


def answer_question(question: str, todos) -> str:
    """Ask Claude to answer `question` grounded in the retrieved `todos`."""
    context = format_todos(todos)
    user_message = (
        f"Here are the user's relevant todos:\n\n{context}\n\n"
        f"Question: {question}"
    )

    response = get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    # The response is a list of content blocks; pull out the text block(s).
    return "".join(b.text for b in response.content if b.type == "text").strip()


__all__ = ["answer_question", "format_todos", "get_client", "MODEL"]
