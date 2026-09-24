import re
import uuid
from typing import Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from app.models.catalog import Product, ProductStatus
from app.models.shop import Shop, ShopStatus


def with_active_shop(query: Query) -> Query:
    """Restrict a Product query to products belonging to an active (non-suspended) shop.
    Product:Shop is many-to-one so this inner join never duplicates rows."""
    return query.join(Shop, Product.shop_id == Shop.id).filter(Shop.status == ShopStatus.active)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:200] or "product"


def unique_product_slug(db: Session, shop_id: uuid.UUID, source: str) -> str:
    """A slug that is free within this shop.

    Slugs are unique per shop, so a seller listing a second "Smocha" used to hit
    a raw integrity error. Suffixing keeps the first-come slug stable and lets
    the duplicate through under -2, -3, and so on.
    """
    base = slugify(source)
    taken = {
        row[0]
        for row in db.query(Product.slug)
        .filter(Product.shop_id == shop_id, Product.slug.like(f"{base}%"))
        .all()
    }
    return _next_free(base, taken)


def allocate_slugs(db: Session, shop_id: uuid.UUID, names: Iterable[str]) -> List[str]:
    """Slugs for a whole batch of new products, all free within the shop.

    unique_product_slug() runs a LIKE query per product, which a bulk import of
    several thousand rows turns into several thousand round trips against a
    table it is itself growing. This reads the shop's slugs once and resolves
    collisions in memory -- including collisions *within* the batch, which the
    per-product version cannot see because the earlier rows aren't committed yet.
    """
    taken = {row[0] for row in db.query(Product.slug).filter(Product.shop_id == shop_id).all()}
    slugs = []
    for name in names:
        slug = _next_free(slugify(name), taken)
        taken.add(slug)
        slugs.append(slug)
    return slugs


def _next_free(base: str, taken: set) -> str:
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


def remaining_product_slots(db: Session, shop: Shop) -> Optional[int]:
    """How many more products this shop may publish, or None for no limit.

    Drafts are free -- the plan caps what a shop shows buyers, not what a seller
    is still working on. That is also what makes a bulk import of thousands of
    rows possible on any plan: they all land as drafts, and the cap applies when
    the seller publishes them.

    Shared by product create, product update and bulk publish so all three agree
    on the number. They didn't before: create checked the cap and update never
    did, so a seller could walk straight past it with a PATCH.
    """
    max_products = shop.subscription.plan.max_products if shop.subscription else None
    if max_products is None:
        return None

    published = (
        db.query(func.count(Product.id))
        .filter(Product.shop_id == shop.id, Product.status != ProductStatus.draft)
        .scalar()
        or 0
    )
    return max(0, max_products - published)
