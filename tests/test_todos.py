import pytest


# --- GET / (authenticated) ---

def test_read_all_no_auth(client):
    response = client.get("/")
    assert response.status_code == 401


def test_read_all_returns_only_own_todos(client, auth_headers, test_todo):
    response = client.get("/", headers=auth_headers)
    assert response.status_code == 200
    todos = response.json()
    assert len(todos) == 1
    assert todos[0]["title"] == "Test Todo"


def test_read_all_empty_for_new_user(client, auth_headers):
    response = client.get("/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


# --- GET /todos/{todo_id} ---

def test_read_todo_found(client, auth_headers, test_todo):
    response = client.get(f"/todos/{test_todo.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_todo.id
    assert data["title"] == "Test Todo"


def test_read_todo_not_found(client, auth_headers):
    response = client.get("/todos/9999", headers=auth_headers)
    assert response.status_code == 404


def test_read_todo_invalid_id(client, auth_headers):
    response = client.get("/todos/0", headers=auth_headers)
    assert response.status_code == 422


# --- POST /todo ---

def test_create_todo_success(client, auth_headers, db):
    payload = {
        "title": "Buy groceries",
        "description": "Milk and eggs",
        "priority": 2,
        "complete": False,
    }
    response = client.post("/todo", json=payload, headers=auth_headers)
    assert response.status_code == 201


def test_create_todo_no_auth(client):
    payload = {
        "title": "Buy groceries",
        "description": "Milk and eggs",
        "priority": 2,
        "complete": False,
    }
    response = client.post("/todo", json=payload)
    assert response.status_code == 401


def test_create_todo_title_too_short(client, auth_headers):
    payload = {
        "title": "Hi",
        "description": "Valid description",
        "priority": 1,
        "complete": False,
    }
    response = client.post("/todo", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_create_todo_priority_out_of_range(client, auth_headers):
    payload = {
        "title": "Valid title",
        "description": "Valid description",
        "priority": 6,
        "complete": False,
    }
    response = client.post("/todo", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_create_todo_description_too_long(client, auth_headers):
    payload = {
        "title": "Valid title",
        "description": "x" * 101,
        "priority": 3,
        "complete": False,
    }
    response = client.post("/todo", json=payload, headers=auth_headers)
    assert response.status_code == 422


# --- PUT /todos/{todo_id} ---

def test_update_todo_success(client, auth_headers, test_todo, db):
    from models import Todos

    payload = {
        "title": "Updated title here",
        "description": "Updated description",
        "priority": 4,
        "complete": True,
    }
    response = client.put(f"/todos/{test_todo.id}", json=payload, headers=auth_headers)
    assert response.status_code == 204
    updated = db.query(Todos).filter(Todos.id == test_todo.id).first()
    assert updated.title == "Updated title here"


def test_update_todo_not_found(client, auth_headers):
    payload = {
        "title": "Updated title here",
        "description": "Updated description",
        "priority": 4,
        "complete": False,
    }
    response = client.put("/todos/9999", json=payload, headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Todo not found."}


# --- DELETE /todos/{todo_id} ---

def test_delete_todo_success(client, auth_headers, test_todo, db):
    from models import Todos

    response = client.delete(f"/todos/{test_todo.id}", headers=auth_headers)
    assert response.status_code == 204
    remaining = db.query(Todos).filter(Todos.id == test_todo.id).first()
    assert remaining is None


def test_delete_todo_not_found(client, auth_headers):
    response = client.delete("/todos/9999", headers=auth_headers)
    assert response.status_code == 404


def test_delete_todo_invalid_id(client, auth_headers):
    response = client.delete("/todos/0", headers=auth_headers)
    assert response.status_code == 422
