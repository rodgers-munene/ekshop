import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.orm import Session

from app.models.analytics import UserEvent, ProductScore, UserPreference, EventType, SearchTerm
from app.models.catalog import Product, ProductStatus


def log_event(
    db: Session,
    session_id: str,
    event_type: EventType,
    user_id: Optional[uuid.UUID] = None,
    product_id: Optional[uuid.UUID] = None,
    category_id: Optional[uuid.UUID] = None,
    query: Optional[str] = None,
    meta: Optional[dict] = None,
) -> None:
    event = UserEvent(
        user_id=user_id,
        session_id=session_id,
        event_type=event_type,
        product_id=product_id,
        category_id=category_id,
        query=query,
        meta=meta,
    )
    db.add(event)

    # update product score counters
    if product_id:
        score = db.query(ProductScore).filter(ProductScore.product_id == product_id).first()
        if not score:
            score = ProductScore(product_id=product_id)
            db.add(score)
            db.flush()

        if event_type == EventType.view:
            score.views_7d = (score.views_7d or 0) + 1
        elif event_type == EventType.click:
            score.clicks_7d = (score.clicks_7d or 0) + 1
        elif event_type == EventType.add_to_cart:
            score.carts_7d = (score.carts_7d or 0) + 1
        elif event_type == EventType.purchase:
            score.purchases_7d = (score.purchases_7d or 0) + 1
        elif event_type == EventType.wishlist:
            score.wishlists_7d = (score.wishlists_7d or 0) + 1

        # trending_score = weighted sum of recent interactions
        trending = (
            (score.views_7d or 0) * 1
            + (score.clicks_7d or 0) * 2
            + (score.carts_7d or 0) * 3
            + (score.wishlists_7d or 0) * 2
            + (score.purchases_7d or 0) * 5
        )
        score.trending_score = str(round(Decimal(str(trending)), 4))

    # update user preference category weights
    if user_id and product_id:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product and product.category_id:
            prefs = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
            if not prefs:
                prefs = UserPreference(
                    user_id=user_id,
                    category_weights={},
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(prefs)
                db.flush()

            weights = dict(prefs.category_weights or {})
            cat_key = str(product.category_id)
            increment = 3 if event_type == EventType.purchase else 1
            weights[cat_key] = weights.get(cat_key, 0) + increment
            prefs.category_weights = weights

    # track search terms
    if event_type == EventType.search and query:
        term = db.query(SearchTerm).filter(SearchTerm.term == query.lower().strip()).first()
        if term:
            term.count_7d = (term.count_7d or 0) + 1
            term.count_30d = (term.count_30d or 0) + 1
        else:
            db.add(SearchTerm(term=query.lower().strip(), count_7d=1, count_30d=1))

    db.commit()


def get_recommendations(
    db: Session,
    user_id: Optional[uuid.UUID] = None,
    limit: int = 20,
) -> List[Product]:
    base = (
        db.query(Product)
        .outerjoin(ProductScore, Product.id == ProductScore.product_id)
        .filter(Product.status == ProductStatus.active)
    )

    preferred_categories: List[str] = []
    price_min: Optional[float] = None
    price_max: Optional[float] = None

    if user_id:
        prefs = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        if prefs:
            if prefs.price_range_min:
                price_min = float(prefs.price_range_min)
            if prefs.price_range_max:
                price_max = float(prefs.price_range_max)
            if prefs.category_weights:
                sorted_cats = sorted(
                    prefs.category_weights.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
                preferred_categories = [c for c, _ in sorted_cats[:5]]

    if price_min is not None:
        base = base.filter(cast(Product.price, NUMERIC) >= price_min)
    if price_max is not None:
        base = base.filter(cast(Product.price, NUMERIC) <= price_max)

    results: List[Product] = []

    # first bucket: preferred-category products ordered by trending
    if preferred_categories:
        cat_ids = [uuid.UUID(c) for c in preferred_categories]
        cat_products = (
            base.filter(Product.category_id.in_(cat_ids))
            .order_by(cast(ProductScore.trending_score, NUMERIC).desc().nulls_last())
            .limit(limit // 2)
            .all()
        )
        results.extend(cat_products)

    # second bucket: fill remaining slots with trending products not already included
    seen = {p.id for p in results}
    remaining = limit - len(results)
    trending = (
        base.filter(~Product.id.in_(seen) if seen else True)
        .order_by(
            cast(ProductScore.trending_score, NUMERIC).desc().nulls_last(),
            Product.created_at.desc(),
        )
        .limit(remaining)
        .all()
    )
    results.extend(trending)

    return results


def get_trending(db: Session, limit: int = 20) -> List[Product]:
    return (
        db.query(Product)
        .join(ProductScore, Product.id == ProductScore.product_id)
        .filter(Product.status == ProductStatus.active)
        .order_by(cast(ProductScore.trending_score, NUMERIC).desc())
        .limit(limit)
        .all()
    )
