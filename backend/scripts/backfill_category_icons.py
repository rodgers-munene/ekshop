"""One-off backfill: set categories.icon_url to a representative product image.

For each leaf category, picks the primary (or first) image of its
highest-popularity active product. Parent categories aggregate over all
their children's products the same way. Leaf categories with zero products
(there are a couple, e.g. "Paint Plumbing") fall back to their parent's
picked image.

Safe to re-run: always recomputes and overwrites icon_url.

Usage: python scripts/backfill_category_icons.py [--dry-run]
"""
import argparse
import sys

sys.path.insert(0, ".")
from sqlalchemy import text

from app.core.database import engine


def best_image_sql(category_id_expr: str) -> str:
    return f"""
        SELECT pi.url
        FROM products p
        JOIN product_images pi ON pi.product_id = p.id
        WHERE p.status = 'active' AND {category_id_expr}
        ORDER BY p.popularity DESC, p.created_at DESC,
                 pi.is_primary DESC, pi.sort_order ASC
        LIMIT 1
    """


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with engine.begin() as conn:
        categories = conn.execute(
            text("SELECT id, name, parent_id FROM categories")
        ).fetchall()

        leaf_icon: dict = {}
        for cat_id, name, parent_id in categories:
            if parent_id is None:
                continue
            row = conn.execute(
                text(best_image_sql("p.category_id = :cid")), {"cid": cat_id}
            ).fetchone()
            leaf_icon[cat_id] = row[0] if row else None

        parent_icon: dict = {}
        for cat_id, name, parent_id in categories:
            if parent_id is not None:
                continue
            row = conn.execute(
                text(
                    best_image_sql(
                        "p.category_id IN (SELECT id FROM categories WHERE parent_id = :cid)"
                    )
                ),
                {"cid": cat_id},
            ).fetchone()
            parent_icon[cat_id] = row[0] if row else None

        # Leaf categories with no products of their own fall back to their parent's icon.
        for cat_id, name, parent_id in categories:
            if parent_id is not None and leaf_icon.get(cat_id) is None:
                leaf_icon[cat_id] = parent_icon.get(parent_id)

        updates = []
        for cat_id, name, parent_id in categories:
            url = leaf_icon[cat_id] if parent_id is not None else parent_icon[cat_id]
            updates.append((cat_id, name, url))

        missing = [name for _, name, url in updates if url is None]

        if args.dry_run:
            for _, name, url in updates:
                print(f"  {name}: {url}")
            if missing:
                print(f"\nNo image found for: {', '.join(missing)}")
            return

        for cat_id, name, url in updates:
            conn.execute(
                text("UPDATE categories SET icon_url = :url WHERE id = :id"),
                {"url": url, "id": cat_id},
            )

    print(f"updated {len(updates)} categories")
    if missing:
        print(f"no image found for: {', '.join(missing)}")


if __name__ == "__main__":
    main()
