import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import NUMERIC
from sqlalchemy.orm import Session

from app.models.analytics import UserEvent, ProductScore, UserPreference, EventType, SearchTerm
from app.models.catalog import Category, Product, ProductStatus
from app.services.catalog import with_active_shop
from app.services.delivery_pricing import get_region

# Overfetch factor for geo-boosted candidate pools: we pull a larger trending-sorted
# batch, then re-rank it by proximity before trimming to the requested limit, so the
# geo boost can promote a nearby product past a farther one without a second query.
GEO_OVERFETCH = 3


def _geo_weight(buyer_county: Optional[str], shop_county: Optional[str]) -> float:
    """Soft ranking boost, not a filter — nearby shops rank higher, far ones just
    sink lower, they never disappear. Lets a Nairobi franchisee's catalog surface
    first for Nairobi buyers without hiding the Nyeri catalog from them."""
    if not buyer_county or not shop_county:
        return 1.0
    if buyer_county.strip().lower() == shop_county.strip().lower():
        return 3.0
    buyer_region = get_region(buyer_county)
    if buyer_region and buyer_region == get_region(shop_county):
        return 1.5
    return 1.0


def _rank_with_geo_boost(products: List[Product], buyer_county: Optional[str], limit: int) -> List[Product]:
    if not buyer_county:
        return products[:limit]

    scored = []
    for idx, p in enumerate(products):
        base = float(p.score.trending_score) if p.score and p.score.trending_score else 0.0
        weight = _geo_weight(buyer_county, p.shop.county if p.shop else None)
        # negative idx as tiebreaker keeps the original trending order for equal scores
        scored.append((base * weight, -idx, p))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [p for _, _, p in scored[:limit]]


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
    buyer_county: Optional[str] = None,
) -> List[Product]:
    # ── Authenticated user with browsing history ──────────────
    if user_id:
        prefs = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
        preferred_categories: List[str] = []
        price_min: Optional[float] = None
        price_max: Optional[float] = None

        if prefs:
            if prefs.price_range_min:
                price_min = float(prefs.price_range_min)
            if prefs.price_range_max:
                price_max = float(prefs.price_range_max)
            if prefs.category_weights:
                sorted_cats = sorted(
                    prefs.category_weights.items(), key=lambda x: x[1], reverse=True
                )
                preferred_categories = [c for c, _ in sorted_cats[:5]]

        base = with_active_shop(
            db.query(Product)
            .outerjoin(ProductScore, Product.id == ProductScore.product_id)
            .filter(Product.status == ProductStatus.active)
        )
        if price_min is not None:
            base = base.filter(cast(Product.price, NUMERIC) >= price_min)
        if price_max is not None:
            base = base.filter(cast(Product.price, NUMERIC) <= price_max)

        results: List[Product] = []
        if preferred_categories:
            cat_ids = [uuid.UUID(c) for c in preferred_categories]
            cat_limit = limit // 2
            candidates = (
                base.filter(Product.category_id.in_(cat_ids))
                .order_by(cast(ProductScore.trending_score, NUMERIC).desc().nulls_last())
                .limit(cat_limit * GEO_OVERFETCH)
                .all()
            )
            results.extend(_rank_with_geo_boost(candidates, buyer_county, cat_limit))

        seen = {p.id for p in results}
        fill_limit = limit - len(results)
        fill_candidates = (
            base.filter(~Product.id.in_(seen) if seen else True)
            .order_by(
                cast(ProductScore.trending_score, NUMERIC).desc().nulls_last(),
                Product.created_at.desc(),
            )
            .limit(fill_limit * GEO_OVERFETCH)
            .all()
        )
        results.extend(_rank_with_geo_boost(fill_candidates, buyer_county, fill_limit))
        return results

    # ── Anonymous visitor: spread evenly across all categories ─
    parent_categories = (
        db.query(Category)
        .filter(Category.parent_id == None, Category.is_active == True)
        .all()
    )

    results = []
    seen: set = set()
    per_cat = max(2, limit // max(len(parent_categories), 1))

    for cat in parent_categories:
        child_ids = [c.id for c in (cat.children or [])]
        all_ids = [cat.id] + child_ids
        candidates = (
            with_active_shop(
                db.query(Product)
                .outerjoin(ProductScore, Product.id == ProductScore.product_id)
                .filter(Product.status == ProductStatus.active, Product.category_id.in_(all_ids))
            )
            .order_by(
                cast(ProductScore.trending_score, NUMERIC).desc().nulls_last(),
                Product.created_at.desc(),
            )
            .limit(per_cat * GEO_OVERFETCH)
            .all()
        )
        products = _rank_with_geo_boost(candidates, buyer_county, per_cat)
        for p in products:
            if p.id not in seen:
                seen.add(p.id)
                results.append(p)

    # fill any remaining slots with trending products not yet included
    if len(results) < limit:
        fill_limit = limit - len(results)
        extra_candidates = (
            with_active_shop(
                db.query(Product)
                .outerjoin(ProductScore, Product.id == ProductScore.product_id)
                .filter(Product.status == ProductStatus.active, ~Product.id.in_(seen))
            )
            .order_by(
                cast(ProductScore.trending_score, NUMERIC).desc().nulls_last(),
                Product.created_at.desc(),
            )
            .limit(fill_limit * GEO_OVERFETCH)
            .all()
        )
        results.extend(_rank_with_geo_boost(extra_candidates, buyer_county, fill_limit))

    return results


def get_trending(db: Session, limit: int = 20, buyer_county: Optional[str] = None) -> List[Product]:
    query = (
        with_active_shop(
            db.query(Product)
            .outerjoin(ProductScore, Product.id == ProductScore.product_id)
            .filter(Product.status == ProductStatus.active)
        )
        .order_by(
            cast(ProductScore.trending_score, NUMERIC).desc().nulls_last(),
            Product.created_at.desc(),
        )
    )
    if not buyer_county:
        return query.limit(limit).all()

    candidates = query.limit(limit * GEO_OVERFETCH).all()
    return _rank_with_geo_boost(candidates, buyer_county, limit)
