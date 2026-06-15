from fastapi import status


def test_return_user(client, auth_headers, test_user):
    response = client.get("/users/", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert data["first_name"] == "Test"
    assert data["last_name"] == "User"
    assert data["role"] == "user"
    assert data["phone_number"] == "555-555-5555"


def test_change_password_success(client, auth_headers, test_user):
    response = client.put(
        "/users/password",
        json={"password": "testpass123", "new_password": "newpassword"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT


def test_change_password_invalid_current_password(client, auth_headers, test_user):
    response = client.put(
        "/users/password",
        json={"password": "wrongpassword", "new_password": "newpassword"},
        headers=auth_headers,
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Error on password change"}


def test_change_phone_number_success(client, auth_headers, test_user):
    response = client.put("/users/change_phone_number/2222222222", headers=auth_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT
