"""
factory-template.py — factory_boy factories for test data generation.

Place factory files at: tests/factories/

Each factory provides:
  - Sensible defaults so tests can create objects with zero arguments
  - Overridable fields for specific test scenarios
  - Sequence-based IDs to avoid collisions
  - Both in-memory (.build()) and DB-persisted (.create()) usage

Dependencies:
  pip install factory-boy
"""

import factory
from datetime import datetime, timezone

from app.models import User, Order, OrderItem


# ─── User Factory ────────────────────────────────────────────────────────────────

class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    """
    Factory for creating User model instances.

    Usage:
        # In-memory (no DB write):
        user = UserFactory.build()

        # Persisted to DB (requires session wiring in conftest):
        user = UserFactory.create()

        # Override defaults:
        admin = UserFactory.build(role="admin", is_active=True)

        # Batch:
        users = UserFactory.build_batch(5)
    """

    class Meta:
        model = User
        sqlalchemy_session = None           # Set per-test via conftest fixture
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: n + 1)
    email = factory.LazyAttribute(lambda obj: f"user{obj.id}@example.com")
    display_name = factory.Faker("name")
    role = "member"
    is_active = True
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))

    class Params:
        """Traits for common variations."""

        admin = factory.Trait(
            role="admin",
            display_name=factory.LazyAttribute(lambda obj: f"Admin {obj.id}"),
        )

        inactive = factory.Trait(
            is_active=False,
        )


# ─── Order Factory ───────────────────────────────────────────────────────────────

class OrderFactory(factory.alchemy.SQLAlchemyModelFactory):
    """
    Factory for creating Order model instances.

    Usage:
        # Basic order (auto-creates a user):
        order = OrderFactory.build()

        # Order for a specific user:
        order = OrderFactory.build(user_id=42)

        # Override status:
        shipped = OrderFactory.build(status="shipped")
    """

    class Meta:
        model = Order
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: n + 1)
    user_id = factory.LazyAttribute(lambda obj: UserFactory.build().id)
    status = "pending"
    total_cents = factory.Faker("random_int", min=500, max=500000)
    currency = "USD"
    notes = None
    created_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    updated_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))

    class Params:
        """Traits for common order states."""

        completed = factory.Trait(
            status="completed",
        )

        cancelled = factory.Trait(
            status="cancelled",
            notes="Cancelled by customer",
        )


# ─── Order Item Factory ──────────────────────────────────────────────────────────

class OrderItemFactory(factory.alchemy.SQLAlchemyModelFactory):
    """
    Factory for creating OrderItem model instances.

    Usage:
        item = OrderItemFactory.build(order_id=1, product_name="Widget")
    """

    class Meta:
        model = OrderItem
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: n + 1)
    order_id = factory.LazyAttribute(lambda obj: OrderFactory.build().id)
    product_name = factory.Faker("word")
    quantity = factory.Faker("random_int", min=1, max=10)
    unit_price_cents = factory.Faker("random_int", min=100, max=50000)


# ─── Usage Examples ──────────────────────────────────────────────────────────────
#
# # Build without persisting (unit tests):
# user = UserFactory.build()
# user = UserFactory.build(role="admin")
# users = UserFactory.build_batch(3)
#
# # Build with trait:
# admin = UserFactory.build(admin=True)
# inactive = UserFactory.build(inactive=True)
#
# # Persisted (integration tests with conftest session wiring):
# user = UserFactory.create()
# order = OrderFactory.create(user_id=user.id)
#
# # Related objects:
# user = UserFactory.create()
# order = OrderFactory.create(user_id=user.id)
# items = OrderItemFactory.create_batch(3, order_id=order.id)
