"""The server copy of the cart is what the abandoned-cart report can see.

The storefront kept the cart in local storage and only pushed it to the server
during checkout, so a basket that was filled and then deserted -- exactly the
basket the admin "cart abandonment" panel exists to find -- left no trace in the
database at all. `PUT /cart/` mirrors the whole cart, and these tests pin the
rules that make that mirror trustworthy:

* it is a replace, and an empty payload really does empty the cart;
* a line that only changed quantity is not re-created, so `added_at` keeps
  meaning "when the shopper first added this" instead of resetting on every
  keystroke and corrupting the conversion window;
* a product that is no longer in the catalogue is dropped instead of turning the
  whole sync into a 500, because the local cart is the only copy of the intent.
"""
import logging
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models.commerce import Cart, CartItem
from app.schemas.commerce import (
    MAX_CART_LINES,
    MAX_CART_QUANTITY,
    CartItemReplace,
    CartReplace,
)


class FakeSession:
    """Enough of a Session for `replace_cart`, which only ever looks up one cart,
    a set of product ids and that cart's items."""

    def __init__(self, carts=None, products=None, items=None):
        self.carts = list(carts or [])
        self.products = list(products or [])
        self.items = list(items or [])
        self.added = []
        self.deleted = []
        self.flushes = 0
        self.commits = 0
        self._criteria = ()

    def query(self, entity):
        self._entity = entity
        self._criteria = ()
        return self

    def filter(self, *criteria):
        self._criteria = criteria
        return self

    def first(self):
        rows = self._rows()
        return rows[0] if rows else None

    def all(self):
        return self._rows()

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, Cart):
            self.carts.append(obj)
        elif isinstance(obj, CartItem):
            self.items.append(obj)

    def delete(self, obj):
        self.deleted.append(obj)
        if isinstance(obj, CartItem) and obj in self.items:
            self.items.remove(obj)

    def flush(self):
        self.flushes += 1

    def commit(self):
        self.commits += 1

    def _rows(self):
        for expr in self._criteria:
            left = expr.left
            # SQLAlchemy hands back an AnnotatedColumn here, not the instrumented
            # attribute, so identify the column by where it lives.
            column = (left.table.name, left.key)
            value = getattr(expr.right, "value", expr.right)
            if column == ("carts", "user_id"):
                return [c for c in self.carts if c.user_id == value]
            if column == ("products", "id"):
                return [(p,) for p in self.products if p in value]
            if column == ("cart_items", "cart_id"):
                return [i for i in self.items if i.cart_id == value]
        raise AssertionError("replace_cart ran a query this fake does not model")


USER_ID = uuid.uuid4()
CART_ID = uuid.uuid4()
FIRST_SEEN = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)


def _cart():
    return Cart(id=CART_ID, user_id=USER_ID)


def _item(product_id, quantity=1, variant_id=None, added_at=FIRST_SEEN):
    return CartItem(
        id=uuid.uuid4(),
        cart_id=CART_ID,
        product_id=product_id,
        variant_id=variant_id,
        quantity=quantity,
        added_at=added_at,
    )


def _replace(payload, session):
    from app.routers.commerce import replace_cart

    return replace_cart(
        payload=payload,
        db=session,
        current_user=SimpleNamespace(id=USER_ID),
    )


def _line(product_id, quantity=1, variant_id=None):
    return CartItemReplace(product_id=product_id, variant_id=variant_id, quantity=quantity)


class TestReplaceSemantics:
    def test_an_empty_payload_empties_the_cart(self):
        kept = _item(uuid.uuid4())
        session = FakeSession(carts=[_cart()], items=[kept])

        _replace(CartReplace(items=[]), session)

        assert session.deleted == [kept]
        assert session.added == []
        assert session.items == []

    def test_a_changed_quantity_keeps_the_line_and_its_added_at(self):
        """The row the shopper already had is edited, not deleted and re-added.
        Re-adding would move `added_at` forward on every change, which is the
        timestamp the abandonment report compares against paid orders."""
        product_id = uuid.uuid4()
        existing = _item(product_id, quantity=1)
        session = FakeSession(carts=[_cart()], products=[product_id], items=[existing])

        _replace(CartReplace(items=[_line(product_id, quantity=4)]), session)

        assert session.deleted == []
        assert session.added == []
        assert existing.quantity == 4
        assert existing.added_at == FIRST_SEEN
        assert existing.id is not None

    def test_an_unchanged_line_is_left_alone(self):
        product_id = uuid.uuid4()
        existing = _item(product_id, quantity=2)
        session = FakeSession(carts=[_cart()], products=[product_id], items=[existing])

        _replace(CartReplace(items=[_line(product_id, quantity=2)]), session)

        assert session.deleted == []
        assert session.added == []

    def test_new_lines_are_inserted_and_missing_lines_are_removed(self):
        kept_id, dropped_id, added_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        kept = _item(kept_id, quantity=1)
        dropped = _item(dropped_id, quantity=1)
        session = FakeSession(
            carts=[_cart()],
            products=[kept_id, dropped_id, added_id],
            items=[kept, dropped],
        )

        _replace(
            CartReplace(items=[_line(kept_id, quantity=1), _line(added_id, quantity=3)]),
            session,
        )

        assert session.deleted == [dropped]
        assert [i.product_id for i in session.added] == [added_id]
        assert session.added[0].quantity == 3
        assert session.added[0].cart_id == CART_ID

    def test_a_variant_is_part_of_the_line_identity(self):
        """Same product, different variant: two lines, not a quantity bump."""
        product_id, variant_id = uuid.uuid4(), uuid.uuid4()
        bare = _item(product_id, quantity=1, variant_id=None)
        session = FakeSession(carts=[_cart()], products=[product_id], items=[bare])

        _replace(
            CartReplace(items=[_line(product_id, quantity=1, variant_id=variant_id)]),
            session,
        )

        assert session.deleted == [bare]
        assert [i.variant_id for i in session.added] == [variant_id]

    def test_repeated_lines_collapse_instead_of_tripping_the_unique_constraint(self):
        """`cart_items` is unique on (cart_id, product_id, variant_id). A payload
        with the same line twice must be folded, not inserted twice."""
        product_id = uuid.uuid4()
        session = FakeSession(carts=[_cart()], products=[product_id])

        _replace(
            CartReplace(items=[_line(product_id, quantity=2), _line(product_id, quantity=3)]),
            session,
        )

        assert len(session.added) == 1
        assert session.added[0].quantity == 5

    def test_an_older_duplicate_row_is_cleaned_up(self):
        """A NULL variant means the database unique constraint never applied, so
        duplicates can already exist in production. A replace tidies them."""
        product_id = uuid.uuid4()
        first, duplicate = _item(product_id, quantity=1), _item(product_id, quantity=1)
        session = FakeSession(
            carts=[_cart()], products=[product_id], items=[first, duplicate]
        )

        _replace(CartReplace(items=[_line(product_id, quantity=1)]), session)

        assert session.deleted == [duplicate]
        assert session.added == []
        assert first.quantity == 1

    def test_the_cart_is_created_for_a_first_time_shopper(self):
        product_id = uuid.uuid4()
        session = FakeSession(products=[product_id])

        cart = _replace(CartReplace(items=[_line(product_id)]), session)

        assert session.flushes == 1
        assert session.commits == 1
        assert [c.user_id for c in session.carts] == [USER_ID]
        assert cart.user_id == USER_ID


class TestUnknownProducts:
    def test_a_delisted_product_is_dropped_rather_than_failing_the_sync(self, caplog):
        """`cart_items.product_id` is a foreign key: inserting a product the
        catalogue no longer has would raise and return 500, and one dead line
        would then stop every other line from being recorded."""
        known_id, gone_id = uuid.uuid4(), uuid.uuid4()
        session = FakeSession(carts=[_cart()], products=[known_id])

        with caplog.at_level(logging.WARNING, logger="app.routers.commerce"):
            _replace(
                CartReplace(items=[_line(known_id, quantity=2), _line(gone_id, quantity=1)]),
                session,
            )

        assert [i.product_id for i in session.added] == [known_id]
        assert "dropped 1 line" in caplog.text

    def test_an_existing_line_for_a_delisted_product_is_removed(self):
        gone_id = uuid.uuid4()
        stale = _item(gone_id, quantity=1)
        session = FakeSession(carts=[_cart()], products=[], items=[stale])

        _replace(CartReplace(items=[_line(gone_id, quantity=1)]), session)

        assert session.deleted == [stale]
        assert session.added == []


class TestPayloadBounds:
    """This route is called automatically after every cart change, so its input
    is a write a client can trigger without the shopper seeing it."""

    @pytest.mark.parametrize("quantity", [0, -1, MAX_CART_QUANTITY + 1])
    def test_impossible_quantities_are_rejected(self, quantity):
        with pytest.raises(ValueError):
            _line(uuid.uuid4(), quantity=quantity)

    def test_a_cart_full_of_lines_is_rejected(self):
        with pytest.raises(ValueError):
            CartReplace(items=[_line(uuid.uuid4()) for _ in range(MAX_CART_LINES + 1)])

    def test_a_cart_at_the_limit_is_allowed(self):
        assert len(CartReplace(items=[_line(uuid.uuid4()) for _ in range(MAX_CART_LINES)]).items) == MAX_CART_LINES

    def test_an_empty_cart_is_valid(self):
        assert CartReplace(items=[]).items == []


class TestRouteRegistration:
    def test_put_on_the_cart_is_exposed(self):
        """The storefront mirrors the cart with PUT /cart/; the id-based PATCH and
        DELETE routes cannot express "this is the whole cart now"."""
        from app.routers.commerce import cart_router

        put_routes = {
            route.path for route in cart_router.routes if "PUT" in route.methods
        }
        assert "/cart/" in put_routes
