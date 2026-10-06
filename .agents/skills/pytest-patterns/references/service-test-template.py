"""
service-test-template.py — Annotated service unit test with mocked repository.

Place at: tests/unit/services/test_user_service.py

This template demonstrates:
  - Testing service business logic in isolation
  - Mocking repositories (the data layer) with AsyncMock
  - Mocking external services (email, notifications)
  - Testing success paths, error paths, and edge cases
  - Using parametrize for input variations

Note on mocking strategy:
  - Mock the repository layer (data access) so service tests run without a DB.
  - Do NOT mock Pydantic validation or domain logic -- let it execute naturally.
  - For integration tests that hit the real DB, see integration-test-template.py.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.user_service import UserService
from app.models import User
from app.exceptions import NotFoundError, ConflictError, ForbiddenError


# ─── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_user_repo():
    """Create a mocked user repository with common async methods."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.list_all = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def user_service(mock_user_repo):
    """Create a UserService with mocked dependencies."""
    return UserService(user_repo=mock_user_repo)


@pytest.fixture
def existing_user():
    """A User object representing an existing user in the system."""
    return User(
        id=1,
        email="alice@example.com",
        display_name="Alice",
        role="member",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ─── Create User Tests ──────────────────────────────────────────────────────────

class TestCreateUser:
    """Tests for UserService.create_user()."""

    async def test_create_user_success(self, user_service, mock_user_repo):
        """Creating a user with a unique email succeeds."""
        # Arrange: email does not exist yet
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.create.return_value = User(
            id=1,
            email="new@example.com",
            display_name="New User",
            role="member",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Act
        result = await user_service.create_user(
            email="new@example.com",
            display_name="New User",
        )

        # Assert
        assert result.email == "new@example.com"
        assert result.display_name == "New User"
        assert result.role == "member"
        mock_user_repo.create.assert_called_once()

    async def test_create_user_duplicate_email_raises(
        self, user_service, mock_user_repo, existing_user
    ):
        """Creating a user with an existing email raises ConflictError."""
        # Arrange: email already exists
        mock_user_repo.get_by_email.return_value = existing_user

        # Act & Assert
        with pytest.raises(ConflictError, match="already exists"):
            await user_service.create_user(
                email="alice@example.com",
                display_name="Duplicate",
            )

        # Verify we never attempted to create
        mock_user_repo.create.assert_not_called()

    @pytest.mark.parametrize("role", ["member", "admin", "viewer"])
    async def test_create_user_with_role(self, user_service, mock_user_repo, role):
        """Users can be created with any valid role."""
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.create.return_value = User(
            id=1, email="test@example.com", display_name="Test",
            role=role, is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        result = await user_service.create_user(
            email="test@example.com",
            display_name="Test",
            role=role,
        )

        assert result.role == role


# ─── Get User Tests ──────────────────────────────────────────────────────────────

class TestGetUser:
    """Tests for UserService.get_user()."""

    async def test_get_user_found(self, user_service, mock_user_repo, existing_user):
        """Returns the user when they exist."""
        mock_user_repo.get_by_id.return_value = existing_user

        result = await user_service.get_user(user_id=1)

        assert result.id == 1
        assert result.email == "alice@example.com"
        mock_user_repo.get_by_id.assert_called_once_with(1)

    async def test_get_user_not_found(self, user_service, mock_user_repo):
        """Raises NotFoundError when user does not exist."""
        mock_user_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError, match="not found"):
            await user_service.get_user(user_id=999)


# ─── Update User Tests ──────────────────────────────────────────────────────────

class TestUpdateUser:
    """Tests for UserService.update_user()."""

    async def test_update_display_name(
        self, user_service, mock_user_repo, existing_user
    ):
        """Updating display_name succeeds."""
        mock_user_repo.get_by_id.return_value = existing_user
        existing_user.display_name = "Updated Alice"
        mock_user_repo.update.return_value = existing_user

        result = await user_service.update_user(
            user_id=1, display_name="Updated Alice"
        )

        assert result.display_name == "Updated Alice"

    async def test_update_nonexistent_user(self, user_service, mock_user_repo):
        """Updating a non-existent user raises NotFoundError."""
        mock_user_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await user_service.update_user(user_id=999, display_name="Ghost")


# ─── Delete User Tests ──────────────────────────────────────────────────────────

class TestDeleteUser:
    """Tests for UserService.delete_user()."""

    async def test_delete_user_success(
        self, user_service, mock_user_repo, existing_user
    ):
        """Deleting an existing user succeeds."""
        mock_user_repo.get_by_id.return_value = existing_user

        await user_service.delete_user(user_id=1)

        mock_user_repo.delete.assert_called_once_with(1)

    async def test_delete_user_not_found(self, user_service, mock_user_repo):
        """Deleting a non-existent user raises NotFoundError."""
        mock_user_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await user_service.delete_user(user_id=999)


# ─── External Service Mocking ───────────────────────────────────────────────────

class TestUserNotifications:
    """Tests for notification side effects during user operations."""

    async def test_welcome_email_sent_on_create(self, user_service, mock_user_repo):
        """A welcome email is sent when a new user is created."""
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.create.return_value = User(
            id=1, email="new@example.com", display_name="New",
            role="member", is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with patch(
            "app.services.user_service.EmailClient"
        ) as mock_email_cls:
            mock_email = mock_email_cls.return_value
            mock_email.send_welcome = AsyncMock(return_value=True)

            await user_service.create_user(
                email="new@example.com", display_name="New"
            )

            mock_email.send_welcome.assert_called_once_with("new@example.com")

    async def test_create_user_succeeds_even_if_email_fails(
        self, user_service, mock_user_repo
    ):
        """User creation should not fail if the welcome email fails."""
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.create.return_value = User(
            id=1, email="new@example.com", display_name="New",
            role="member", is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        with patch(
            "app.services.user_service.EmailClient"
        ) as mock_email_cls:
            mock_email = mock_email_cls.return_value
            mock_email.send_welcome = AsyncMock(
                side_effect=Exception("SMTP error")
            )

            # Should NOT raise despite email failure
            result = await user_service.create_user(
                email="new@example.com", display_name="New"
            )
            assert result.email == "new@example.com"
