"""Local text embeddings using sentence-transformers.

An *embedding* is a fixed-length list of floats that captures the *meaning* of a
piece of text. Texts with similar meaning produce vectors that are close together
(by cosine distance); unrelated texts produce vectors that are far apart. That is
what lets us do "find the todos most similar to this question" in Postgres.

We use `all-MiniLM-L6-v2`, which maps any text to a 384-dimensional vector. The
model runs entirely on your machine — no API key, no network at inference time.
"""

from sentence_transformers import SentenceTransformer

from models import EMBEDDING_DIM

MODEL_NAME = "all-MiniLM-L6-v2"

# Loading the model is slow (and downloads ~80MB the first time), so we load it
# once and reuse it. `_model` is filled lazily on first use.
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Return the shared model instance, loading it on first call."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embed_text(text: str) -> list[float]:
    """Turn a string into its 384-dim embedding vector."""
    vector = get_model().encode(text)
    return vector.tolist()


def todo_to_text(title: str, description: str) -> str:
    """Combine a todo's fields into the single string we embed.

    Title and description together describe what the todo is about, so we embed
    both. Keeping this in one place means create, update, search, and backfill all
    embed text the same way.
    """
    return f"{title}\n\n{description}".strip()


__all__ = ["embed_text", "todo_to_text", "get_model", "EMBEDDING_DIM", "MODEL_NAME"]
