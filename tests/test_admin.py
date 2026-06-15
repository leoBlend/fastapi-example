from fastapi import status


def test_admin_read_all_authenticated(client, admin_auth_headers, test_todo):
    response = client.get("/admin/todo", headers=admin_auth_headers)
    assert response.status_code == status.HTTP_200_OK
    todos = response.json()
    assert len(todos) >= 1
    assert todos[0]["title"] == "Test Todo"


def test_admin_read_all_not_admin(client, auth_headers):
    response = client.get("/admin/todo", headers=auth_headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_admin_delete_todo(client, admin_auth_headers, test_todo, db):
    from models import Todos

    response = client.delete(f"/admin/todo/{test_todo.id}", headers=admin_auth_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    remaining = db.query(Todos).filter(Todos.id == test_todo.id).first()
    assert remaining is None


def test_admin_delete_todo_not_found(client, admin_auth_headers):
    response = client.delete("/admin/todo/9999", headers=admin_auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Todo not found."}
