"""Tests for the RAG layer (/rag/search and /rag/ask).

Embeddings and Claude are stubbed by fixtures in conftest.py (`mock_embeddings`
is autouse; `mock_claude` is opt-in), so these run fast and offline.
"""


def _make_todo(client, headers, title, description, priority=3):
    resp = client.post(
        "/todo",
        json={"title": title, "description": description, "priority": priority, "complete": False},
        headers=headers,
    )
    assert resp.status_code == 201


# --- auth -------------------------------------------------------------------

def test_search_requires_auth(client):
    assert client.get("/rag/search", params={"q": "anything"}).status_code == 401


def test_ask_requires_auth(client):
    assert client.post("/rag/ask", json={"question": "anything"}).status_code == 401


# --- search (retrieval) -----------------------------------------------------

def test_search_returns_results_ordered_by_distance(client, auth_headers):
    _make_todo(client, auth_headers, "Fix server", "the api is down")
    _make_todo(client, auth_headers, "Buy milk", "groceries from the store")
    _make_todo(client, auth_headers, "Call dentist", "schedule a checkup")

    resp = client.get("/rag/search", params={"q": "Buy milk\n\ngroceries from the store", "k": 3}, headers=auth_headers)
    assert resp.status_code == 200
    hits = resp.json()
    assert len(hits) == 3
    # Distances must be non-decreasing (nearest first).
    distances = [h["distance"] for h in hits]
    assert distances == sorted(distances)
    # An exact-text query embeds identically to that todo -> distance ~0, ranked first.
    assert hits[0]["title"] == "Buy milk"
    assert hits[0]["distance"] < 1e-6


def test_search_respects_k_limit(client, auth_headers):
    for i in range(5):
        _make_todo(client, auth_headers, f"Task {i}", f"description number {i}")
    resp = client.get("/rag/search", params={"q": "task", "k": 2}, headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_search_is_user_scoped(client, auth_headers, admin_auth_headers):
    # admin creates a todo; the regular user must not see it in their search.
    _make_todo(client, admin_auth_headers, "Admin secret", "only admin should see this")
    _make_todo(client, auth_headers, "User task", "belongs to the regular user")

    resp = client.get("/rag/search", params={"q": "secret", "k": 10}, headers=auth_headers)
    assert resp.status_code == 200
    titles = [h["title"] for h in resp.json()]
    assert "Admin secret" not in titles
    assert "User task" in titles


# --- ask (full RAG) ---------------------------------------------------------

def test_ask_returns_answer_and_sources(client, auth_headers, mock_claude):
    _make_todo(client, auth_headers, "Pay rent", "transfer rent to landlord by the 1st")

    resp = client.post("/rag/ask", json={"question": "when is rent due?"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "STUB ANSWER for: when is rent due?"
    assert any(s["title"] == "Pay rent" for s in body["sources"])
    # The retrieved todos were actually passed to the generation step.
    assert "Pay rent" in mock_claude["todos"]


def test_ask_validates_empty_question(client, auth_headers):
    assert client.post("/rag/ask", json={"question": ""}, headers=auth_headers).status_code == 422
