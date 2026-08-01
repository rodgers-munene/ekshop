from sqlalchemy.orm import Query

from app.models.catalog import Product
from app.models.shop import Shop, ShopStatus


def with_active_shop(query: Query) -> Query:
    """Restrict a Product query to products belonging to an active (non-suspended) shop.
    Product:Shop is many-to-one so this inner join never duplicates rows."""
    return query.join(Shop, Product.shop_id == Shop.id).filter(Shop.status == ShopStatus.active)
