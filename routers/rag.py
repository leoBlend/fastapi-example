"""RAG endpoints: semantic search over todos, and a grounded Q&A endpoint.

GET  /rag/search?q=...&k=5  -> retrieval only (vector search). No LLM, no API key.
POST /rag/ask  {question}    -> full RAG: retrieve relevant todos, then have Claude
                               answer using only those todos.

Both are scoped to the logged-in user, so you only ever search/answer over your
own todos (same owner_id filter the todos router uses).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from starlette import status

from models import Todos
from database import SessionLocal
from .auth import get_current_user
from embeddings import embed_text
import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[SessionLocal, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


def _retrieve(db, owner_id: int, query: str, k: int):
    """Return the user's todos nearest to `query` by cosine distance.

    `cosine_distance` is provided by pgvector: smaller = more similar. We embed
    the query with the SAME model used to embed todos, then let Postgres do the
    nearest-neighbour ranking. Rows without an embedding are skipped.
    """
    query_vec = embed_text(query)
    return (
        db.query(Todos, Todos.embedding.cosine_distance(query_vec).label("distance"))
        .filter(Todos.owner_id == owner_id, Todos.embedding.isnot(None))
        .order_by("distance")
        .limit(k)
        .all()
    )


class SearchHit(BaseModel):
    id: int
    title: str
    description: str
    priority: int
    complete: bool
    distance: float  # 0 = identical meaning, larger = less similar


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class AskResponse(BaseModel):
    answer: str
    sources: list[SearchHit]


@router.get("/search", status_code=status.HTTP_200_OK, response_model=list[SearchHit])
async def search(
    user: user_dependency,
    db: db_dependency,
    q: str = Query(min_length=1, description="Natural-language query"),
    k: int = Query(default=5, gt=0, le=20, description="How many results"),
):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth failed.")

    results = _retrieve(db, user.get("id"), q, k)
    logger.info("RAG search by user %s: %r -> %d hits", user.get("username"), q, len(results))
    return [
        SearchHit(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            priority=todo.priority,
            complete=todo.complete,
            distance=float(distance),
        )
        for todo, distance in results
    ]


@router.post("/ask", status_code=status.HTTP_200_OK, response_model=AskResponse)
async def ask(user: user_dependency, db: db_dependency, body: AskRequest):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth failed.")

    # 1. RETRIEVE: find the todos most relevant to the question.
    results = _retrieve(db, user.get("id"), body.question, k=5)
    todos = [todo for todo, _distance in results]

    # 2. GENERATE: have Claude answer using only those todos.
    answer = rag_service.answer_question(body.question, todos)
    logger.info("RAG ask by user %s: %r", user.get("username"), body.question)

    sources = [
        SearchHit(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            priority=todo.priority,
            complete=todo.complete,
            distance=float(distance),
        )
        for todo, distance in results
    ]
    return AskResponse(answer=answer, sources=sources)
