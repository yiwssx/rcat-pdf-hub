"""
integration-test-template.py — Integration test with real database.

Place at: tests/integration/test_user_integration.py

This template demonstrates:
  - Full round-trip testing: service -> repository -> database -> assertions
  - Using a real test database (SQLite in-memory via conftest fixtures)
  - Testing data persistence, relationships, and query behavior
  - No mocks -- every layer executes real code

When to use integration tests vs unit tests:
  - Unit tests (service-test-template.py): Fast, mock the repo, test business logic.
  - Integration tests (this file): Slower, real DB, test that layers work together.
  - Both are needed: unit tests for logic coverage, integration tests for confidence.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService
from app.services.order_service import OrderService
from app.repositories.user_repository import UserRepository
from app.repositories.order_repository import OrderRepository
from app.exceptions import NotFoundError, ConflictError


# ─── Mark the entire module as integration tests ─────────────────────────────────
pytestmark = [pytest.mark.integration]


# ─── Fixtures ────────────────────────────────────────────────────────────────────

@pytest.fixture
def user_repo(db_session: AsyncSession):
    """Real user repository backed by the test database."""
    return UserRepository(db_session)


@pytest.fixture
def order_repo(db_session: AsyncSession):
    """Real order repository backed by the test database."""
    return OrderRepository(db_session)


@pytest.fixture
def user_service(user_repo):
    """UserService wired to the real repository."""
    return UserService(user_repo=user_repo)


@pytest.fixture
def order_service(order_repo, user_repo):
    """OrderService wired to real repositories."""
    return OrderService(order_repo=order_repo, user_repo=user_repo)


# ─── User CRUD Integration Tests ─────────────────────────────────────────────────

class TestUserCRUDIntegration:
    """Full round-trip CRUD tests for users with real database."""

    async def test_create_and_retrieve_user(self, user_service):
        """Create a user and verify it can be retrieved."""
        # Create
        created = await user_service.create_user(
            email="integration@example.com",
            display_name="Integration User",
        )
        assert created.id is not None

        # Retrieve
        fetched = await user_service.get_user(created.id)
        assert fetched.email == "integration@example.com"
        assert fetched.display_name == "Integration User"
        assert fetched.is_active is True

    async def test_update_user_persists(self, user_service):
        """Update a user and verify changes are persisted."""
        # Create
        user = await user_service.create_user(
            email="update-test@example.com",
            display_name="Before Update",
        )

        # Update
        updated = await user_service.update_user(
            user_id=user.id,
            display_name="After Update",
        )
        assert updated.display_name == "After Update"

        # Re-fetch to confirm persistence
        refetched = await user_service.get_user(user.id)
        assert refetched.display_name == "After Update"

    async def test_delete_user_removes_from_db(self, user_service):
        """Delete a user and verify they are gone."""
        user = await user_service.create_user(
            email="delete-test@example.com",
            display_name="To Delete",
        )

        await user_service.delete_user(user.id)

        with pytest.raises(NotFoundError):
            await user_service.get_user(user.id)

    async def test_duplicate_email_raises_conflict(self, user_service):
        """Creating two users with the same email raises ConflictError."""
        await user_service.create_user(
            email="unique@example.com",
            display_name="First",
        )

        with pytest.raises(ConflictError, match="already exists"):
            await user_service.create_user(
                email="unique@example.com",
                display_name="Second",
            )


# ─── Relationship Integration Tests ──────────────────────────────────────────────

class TestOrderUserRelationship:
    """Test that orders and users relate correctly in the database."""

    async def test_create_order_for_user(self, user_service, order_service):
        """Create an order linked to a real user."""
        user = await user_service.create_user(
            email="buyer@example.com",
            display_name="Buyer",
        )

        order = await order_service.create_order(
            user_id=user.id,
            items=[{"product_name": "Widget", "quantity": 2, "unit_price_cents": 1500}],
        )

        assert order.user_id == user.id
        assert order.status == "pending"
        assert order.total_cents == 3000  # 2 * 1500

    async def test_user_orders_list(self, user_service, order_service):
        """Retrieve all orders belonging to a user."""
        user = await user_service.create_user(
            email="multi-order@example.com",
            display_name="Frequent Buyer",
        )

        await order_service.create_order(
            user_id=user.id,
            items=[{"product_name": "A", "quantity": 1, "unit_price_cents": 100}],
        )
        await order_service.create_order(
            user_id=user.id,
            items=[{"product_name": "B", "quantity": 1, "unit_price_cents": 200}],
        )

        orders = await order_service.list_orders_for_user(user.id)
        assert len(orders) == 2

    async def test_order_for_nonexistent_user_fails(self, order_service):
        """Creating an order for a user that does not exist raises NotFoundError."""
        with pytest.raises(NotFoundError, match="not found"):
            await order_service.create_order(
                user_id=99999,
                items=[{"product_name": "X", "quantity": 1, "unit_price_cents": 100}],
            )


# ─── Query and Pagination Integration Tests ──────────────────────────────────────

class TestUserQueryIntegration:
    """Test query behavior with real data in the database."""

    async def test_list_users_returns_created_users(self, user_service):
        """List endpoint returns users that were created."""
        await user_service.create_user(email="list1@example.com", display_name="One")
        await user_service.create_user(email="list2@example.com", display_name="Two")

        users = await user_service.list_users(limit=10)

        emails = [u.email for u in users]
        assert "list1@example.com" in emails
        assert "list2@example.com" in emails

    async def test_list_users_respects_limit(self, user_service):
        """List endpoint respects the limit parameter."""
        for i in range(5):
            await user_service.create_user(
                email=f"limit{i}@example.com",
                display_name=f"User {i}",
            )

        users = await user_service.list_users(limit=2)
        assert len(users) <= 2


# ─── Transaction Isolation Verification ───────────────────────────────────────────

class TestTransactionIsolation:
    """Verify that test isolation works -- each test starts with a clean state."""

    async def test_first_creates_user(self, user_service):
        """This test creates a user. The next test should NOT see it."""
        await user_service.create_user(
            email="isolation@example.com",
            display_name="Isolated",
        )
        user = await user_service.get_user_by_email("isolation@example.com")
        assert user is not None

    async def test_second_does_not_see_first(self, user_service):
        """The user from the previous test should not exist (transaction rolled back)."""
        with pytest.raises(NotFoundError):
            await user_service.get_user_by_email("isolation@example.com")
