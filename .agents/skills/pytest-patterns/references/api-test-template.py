"""
api-test-template.py — Annotated API integration test using httpx.AsyncClient.

Place at: tests/integration/test_users_api.py

This template demonstrates:
  - Testing all CRUD endpoints for a resource
  - Auth/unauth request paths
  - Error response assertions (404, 409, 422)
  - Pagination testing
  - Using fixtures for test data

Prerequisites:
  - Root conftest.py provides: client, authenticated_client, admin_client, db_session
  - factories/ provides: UserFactory
"""

import pytest
from httpx import AsyncClient


# ─── Mark the entire module as integration tests ─────────────────────────────────
pytestmark = [pytest.mark.integration]


class TestCreateUser:
    """POST /api/v1/users"""

    async def test_create_user_success(self, authenticated_client: AsyncClient):
        """Authenticated user can create a new user with valid data."""
        payload = {
            "email": "newuser@example.com",
            "display_name": "New User",
            "role": "member",
        }

        response = await authenticated_client.post("/api/v1/users", json=payload)

        # Assert status first, then body
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["display_name"] == "New User"
        assert data["role"] == "member"
        assert "id" in data                     # Don't assert exact ID
        assert "created_at" in data             # Don't assert exact timestamp

    async def test_create_user_duplicate_email(
        self, authenticated_client: AsyncClient, sample_user
    ):
        """Creating a user with an existing email returns 409 Conflict."""
        payload = {
            "email": sample_user.email,         # Already exists
            "display_name": "Duplicate",
        }

        response = await authenticated_client.post("/api/v1/users", json=payload)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    async def test_create_user_invalid_email(self, authenticated_client: AsyncClient):
        """Invalid email format returns 422 Unprocessable Entity."""
        payload = {
            "email": "not-an-email",
            "display_name": "Bad Email",
        }

        response = await authenticated_client.post("/api/v1/users", json=payload)

        assert response.status_code == 422

    async def test_create_user_unauthenticated(self, client: AsyncClient):
        """Unauthenticated request returns 401."""
        payload = {"email": "test@example.com", "display_name": "Test"}

        response = await client.post("/api/v1/users", json=payload)

        assert response.status_code == 401


class TestListUsers:
    """GET /api/v1/users"""

    async def test_list_users_success(self, authenticated_client: AsyncClient):
        """Returns a paginated list of users."""
        response = await authenticated_client.get("/api/v1/users?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)
        assert "next_cursor" in data
        assert "has_more" in data

    async def test_list_users_pagination(self, authenticated_client: AsyncClient):
        """Pagination returns correct page size."""
        response = await authenticated_client.get("/api/v1/users?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 2

    async def test_list_users_with_cursor(
        self, authenticated_client: AsyncClient, sample_user
    ):
        """Cursor-based pagination returns next page."""
        # Get first page
        first_page = await authenticated_client.get("/api/v1/users?limit=1")
        cursor = first_page.json().get("next_cursor")

        if cursor:
            second_page = await authenticated_client.get(
                f"/api/v1/users?limit=1&cursor={cursor}"
            )
            assert second_page.status_code == 200


class TestGetUser:
    """GET /api/v1/users/{user_id}"""

    async def test_get_user_success(
        self, authenticated_client: AsyncClient, sample_user
    ):
        """Returns the user when they exist."""
        response = await authenticated_client.get(f"/api/v1/users/{sample_user.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_user.id
        assert data["email"] == sample_user.email

    async def test_get_user_not_found(self, authenticated_client: AsyncClient):
        """Returns 404 for a non-existent user ID."""
        response = await authenticated_client.get("/api/v1/users/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestUpdateUser:
    """PATCH /api/v1/users/{user_id}"""

    async def test_update_user_success(
        self, authenticated_client: AsyncClient, sample_user
    ):
        """Partial update succeeds with valid data."""
        response = await authenticated_client.patch(
            f"/api/v1/users/{sample_user.id}",
            json={"display_name": "Updated Name"},
        )

        assert response.status_code == 200
        assert response.json()["display_name"] == "Updated Name"

    async def test_update_user_not_found(self, authenticated_client: AsyncClient):
        """Updating a non-existent user returns 404."""
        response = await authenticated_client.patch(
            "/api/v1/users/99999",
            json={"display_name": "Ghost"},
        )

        assert response.status_code == 404


class TestDeleteUser:
    """DELETE /api/v1/users/{user_id}"""

    async def test_delete_user_admin_success(
        self, admin_client: AsyncClient, sample_user
    ):
        """Admin can delete a user."""
        response = await admin_client.delete(f"/api/v1/users/{sample_user.id}")

        assert response.status_code == 204

    async def test_delete_user_non_admin_forbidden(
        self, authenticated_client: AsyncClient, sample_user
    ):
        """Non-admin cannot delete a user."""
        response = await authenticated_client.delete(
            f"/api/v1/users/{sample_user.id}"
        )

        assert response.status_code == 403

    async def test_delete_user_not_found(self, admin_client: AsyncClient):
        """Deleting a non-existent user returns 404."""
        response = await admin_client.delete("/api/v1/users/99999")

        assert response.status_code == 404
