"""
One-time migration: MySQL/PHP Ekshop → PostgreSQL/FastAPI Ekshop

Usage:
    python migrate.py \
        --mysql-host localhost \
        --mysql-user root \
        --mysql-password secret \
        --mysql-db ekshafmy_vapestore \
        --postgres-url postgresql://user:pass@host/ekshop

Skips records that already exist (idempotent on re-run).
"""

import argparse
import json
import re
import sys
import uuid
import logging
from datetime import timezone
from decimal import Decimal

import pymysql
import pymysql.cursors
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text or "item"


def unique_slug(base: str, existing: set) -> str:
    slug = slugify(base)
    candidate = slug
    n = 1
    while candidate in existing:
        candidate = f"{slug}-{n}"
        n += 1
    existing.add(candidate)
    return candidate


def fix_bcrypt(php_hash: str) -> str:
    """PHP uses $2y$ prefix; Python bcrypt uses $2b$. Functionally identical."""
    if php_hash.startswith("$2y$"):
        return "$2b$" + php_hash[4:]
    return php_hash


def map_old_role(role: str) -> str:
    if role in ("seller", "admin"):
        return role
    return "buyer"


def map_order_status(payment_status: str, delivery_status: str):
    """Return (order_group_status, order_status) for the new schema."""
    ds = (delivery_status or "").lower()
    ps = (payment_status or "").lower()
    if "delivered" in ds or "confirmed" in ps:
        return "paid", "delivered"
    if "in_transit" in ds:
        return "paid", "shipped"
    if "picked" in ds:
        return "paid", "processing"
    if "paid" in ps or "confirmed" in ps:
        return "paid", "confirmed"
    return "pending_payment", "pending"


# ── main migration ──────────────────────────────────────────────────────────────

def run(mysql_cfg: dict, postgres_url: str):
    # ── connect ──
    my = pymysql.connect(
        host=mysql_cfg["host"],
        port=mysql_cfg.get("port", 3306),
        user=mysql_cfg["user"],
        password=mysql_cfg["password"],
        database=mysql_cfg["db"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    engine = create_engine(postgres_url)

    # maps: old identifier → new UUID
    user_map: dict[str, uuid.UUID] = {}     # email → uuid
    shop_map: dict[int, uuid.UUID] = {}     # business_id → uuid
    cat_map: dict[str, uuid.UUID] = {}      # subcategory slug → uuid
    parent_cat_map: dict[str, uuid.UUID] = {}  # parent category slug → uuid
    product_map: dict[int, uuid.UUID] = {}     # old bigint id → uuid
    product_shop_map: dict[uuid.UUID, uuid.UUID] = {}  # new product uuid → shop uuid

    used_slugs: set[str] = set()

    with my.cursor() as cur, Session(engine) as db:

        # ── 1. USERS ──────────────────────────────────────────────────────────
        log.info("Migrating users...")
        # load already-migrated users into map in one query
        for row in db.execute(text("SELECT id, email FROM users")).fetchall():
            user_map[row[1].lower()] = row[0]

        cur.execute("SELECT * FROM users")
        rows = cur.fetchall()
        inserted = 0
        for r in rows:
            email = r["email"].strip().lower()
            if email in user_map:
                continue
            uid = uuid.uuid4()
            db.execute(text("""
                INSERT INTO users
                    (id, email, password_hash, first_name, last_name,
                     phone, county, role, status, created_at)
                VALUES
                    (:id, :email, :pw, :fn, :ln,
                     :phone, :county, :role, :status, :ca)
            """), {
                "id": uid,
                "email": email,
                "pw": fix_bcrypt(r["password"]),
                "fn": r["first_name"],
                "ln": r["last_name"],
                "phone": r["phone_no"],
                "county": r.get("county") or "Kenya",
                "role": map_old_role(r.get("role") or "buyer"),
                "status": r.get("status") or "active",
                "ca": r["created_at"],
            })
            user_map[email] = uid
            inserted += 1

        db.commit()
        log.info(f"  Users: {inserted} inserted, {len(user_map)-inserted} already existed")

        # ── 2. CATEGORIES ─────────────────────────────────────────────────────
        log.info("Migrating categories...")
        # load existing categories into maps
        for row in db.execute(text("SELECT id, slug, parent_id FROM categories")).fetchall():
            if row[2] is None:
                # it's a parent — reverse-map slug back to original key
                parent_cat_map[row[1].replace("-", "_")] = row[0]
            else:
                cat_map[row[1].replace("-", "_")] = row[0]
            used_slugs.add(row[1])

        cur.execute("SELECT * FROM categories ORDER BY id")
        cat_rows = cur.fetchall()

        parent_names = sorted({r["category"] for r in cat_rows if r["category"]})
        for pname in parent_names:
            pslug = slugify(pname)
            if pslug in used_slugs:
                continue
            pid = uuid.uuid4()
            display = pname.replace("_", " ").title()
            db.execute(text("""
                INSERT INTO categories (id, name, slug, parent_id, is_active, created_at)
                VALUES (:id, :name, :slug, NULL, TRUE, NOW())
            """), {"id": pid, "name": display, "slug": pslug})
            parent_cat_map[pname] = pid
            used_slugs.add(pslug)

        db.commit()

        for r in cat_rows:
            sub_slug = slugify(r["subcategory"])
            if sub_slug in used_slugs:
                continue
            cid = uuid.uuid4()
            display = r["subcategory"].replace("_", " ").title()
            parent_id = parent_cat_map.get(r["category"])
            db.execute(text("""
                INSERT INTO categories (id, name, slug, parent_id, is_active, created_at)
                VALUES (:id, :name, :slug, :parent_id, TRUE, NOW())
            """), {"id": cid, "name": display, "slug": sub_slug, "parent_id": parent_id})
            cat_map[r["subcategory"]] = cid
            used_slugs.add(sub_slug)

        db.commit()
        log.info(f"  Categories: {len(parent_cat_map)} parents, {len(cat_map)} subcategories")

        # ── 3. SHOPS ──────────────────────────────────────────────────────────
        log.info("Migrating shops...")
        cur.execute("SELECT * FROM business_details ORDER BY business_id")
        biz_rows = cur.fetchall()
        # load already-migrated shops: seller_id → shop uuid
        existing_shops: dict[uuid.UUID, uuid.UUID] = {}
        for row in db.execute(text("SELECT id, seller_id, slug FROM shops")).fetchall():
            existing_shops[row[1]] = row[0]
            used_slugs.add(row[2])

        inserted = 0
        for r in biz_rows:
            email = (r["email"] or "").strip().lower()
            seller_id = user_map.get(email)
            if not seller_id:
                log.warning(f"  Shop '{r['business_name']}': seller {email} not found, skipping")
                continue

            if seller_id in existing_shops:
                shop_map[r["business_id"]] = existing_shops[seller_id]
                continue

            sid = uuid.uuid4()
            slug = unique_slug(r["business_name"], used_slugs)
            exact_location = ", ".join(
                p for p in [r.get("exact_location"), r.get("apartment")] if p
            ) or None

            db.execute(text("""
                INSERT INTO shops
                    (id, seller_id, name, slug, county, exact_location,
                     is_verified, status, rating_avg, rating_count, total_sales,
                     created_at, updated_at)
                VALUES
                    (:id, :seller_id, :name, :slug, :county, :exact_location,
                     FALSE, 'active', '0.00', 0, 0, NOW(), NOW())
            """), {
                "id": sid,
                "seller_id": seller_id,
                "name": r["business_name"],
                "slug": slug,
                "county": r.get("business_location1") or "Kenya",
                "exact_location": exact_location,
            })
            shop_map[r["business_id"]] = sid

            # payment methods
            methods = [
                r.get("payment_method"),
                r.get("payment1_method"),
                r.get("payment2_method"),
            ]
            for i, m in enumerate(methods):
                if m and m.strip():
                    db.execute(text("""
                        INSERT INTO shop_payment_methods
                            (id, shop_id, method, is_primary, created_at)
                        VALUES (:id, :shop_id, :method, :is_primary, NOW())
                    """), {
                        "id": uuid.uuid4(),
                        "shop_id": sid,
                        "method": m.strip(),
                        "is_primary": i == 0,
                    })

            inserted += 1

        db.commit()
        log.info(f"  Shops: {inserted} inserted, {len(biz_rows)-inserted} skipped/existed")

        # build email → shop_id map for product lookup
        email_to_shop: dict[str, uuid.UUID] = {}
        cur.execute("SELECT email, business_id FROM business_details")
        for r in cur.fetchall():
            e = (r["email"] or "").strip().lower()
            if r["business_id"] in shop_map:
                email_to_shop[e] = shop_map[r["business_id"]]

        # ── 4. PRODUCTS ───────────────────────────────────────────────────────
        log.info("Migrating products...")
        # load existing products by slug to avoid re-inserting
        # key: (shop_id, name_lower) → already migrated
        existing_products: set[tuple] = set()
        for row in db.execute(text("SELECT id, slug, shop_id, name FROM products")).fetchall():
            existing_products.add((str(row[2]), row[3].lower()))
            product_shop_map[row[0]] = row[2]
            used_slugs.add(row[1])

        cur.execute("SELECT * FROM products ORDER BY id")
        prod_rows = cur.fetchall()
        inserted = 0
        for r in prod_rows:
            seller_email = (r["email"] or "").strip().lower()
            shop_id = email_to_shop.get(seller_email)
            if not shop_id:
                continue

            if (str(shop_id), r["name"].lower()) in existing_products:
                continue

            category_id = cat_map.get(r.get("category") or "")
            price = str(Decimal(str(r["price"] or 0)))
            slug = unique_slug(r["name"], used_slugs)
            stock = 10 if (r.get("in_stock") or "yes") == "yes" else 0

            pid = uuid.uuid4()
            db.execute(text("""
                INSERT INTO products
                    (id, shop_id, category_id, name, slug, description,
                     price, stock_qty, status, created_at, updated_at)
                VALUES
                    (:id, :shop_id, :cat_id, :name, :slug, :desc,
                     :price, :stock, 'active', :ca, :ca)
            """), {
                "id": pid,
                "shop_id": shop_id,
                "cat_id": category_id,
                "name": r["name"],
                "slug": slug,
                "desc": r.get("description"),
                "price": price,
                "stock": stock,
                "ca": r["created_at"],
            })
            product_map[r["id"]] = pid
            product_shop_map[pid] = shop_id
            inserted += 1

        db.commit()
        log.info(f"  Products: {inserted} inserted, {len(prod_rows)-inserted} skipped")

        # ── 5. PRODUCT IMAGES ─────────────────────────────────────────────────
        log.info("Migrating product images...")
        cur.execute("SELECT * FROM product_images ORDER BY id")
        img_rows = cur.fetchall()
        inserted = 0
        # track which product has already had a primary image assigned
        has_primary: set[uuid.UUID] = set()
        for r in img_rows:
            new_pid = product_map.get(r["product_id"])
            if not new_pid:
                continue
            is_primary = new_pid not in has_primary
            if is_primary:
                has_primary.add(new_pid)
            db.execute(text("""
                INSERT INTO product_images
                    (id, product_id, url, thumbnail_url, is_primary, sort_order, created_at)
                VALUES
                    (:id, :pid, :url, :thumb, :primary, :sort, NOW())
            """), {
                "id": uuid.uuid4(),
                "pid": new_pid,
                "url": r["image_path"],
                "thumb": r.get("thumbnail_path"),
                "primary": is_primary,
                "sort": 0,
            })
            inserted += 1

        db.commit()
        log.info(f"  Product images: {inserted} inserted")

        # ── 6. PRODUCT REVIEWS ────────────────────────────────────────────────
        log.info("Migrating product reviews...")
        cur.execute("SELECT * FROM product_reviews ORDER BY id")
        review_rows = cur.fetchall()
        inserted = skipped = 0
        for r in review_rows:
            new_pid = product_map.get(r["product_id"])
            reviewer_id = user_map.get((r["user_email"] or "").strip().lower())
            if not new_pid or not reviewer_id:
                skipped += 1
                continue
            shop_id = product_shop_map.get(new_pid)
            if not shop_id:
                skipped += 1
                continue
            db.execute(text("""
                INSERT INTO product_reviews
                    (id, product_id, buyer_id, shop_id, rating, body, created_at)
                VALUES (:id, :pid, :uid, :shop_id, :rating, :body, :ca)
                ON CONFLICT DO NOTHING
            """), {
                "id": uuid.uuid4(),
                "pid": new_pid,
                "uid": reviewer_id,
                "shop_id": shop_id,
                "rating": r["rating"],
                "body": r.get("review"),
                "ca": r["created_at"],
            })
            inserted += 1

        db.commit()
        log.info(f"  Reviews: {inserted} inserted, {skipped} skipped (missing product/user)")

        # ── 7. ORDERS ─────────────────────────────────────────────────────────
        log.info("Migrating orders...")
        cur.execute("SELECT * FROM order_summary ORDER BY order_date")
        order_rows = cur.fetchall()

        # group rows by order_group_id (use order row id as fallback)
        from collections import defaultdict
        groups: dict[str, list] = defaultdict(list)
        for r in order_rows:
            gid = r.get("order_group_id") or f"solo-{r['id']}"
            groups[gid].append(r)

        og_inserted = o_inserted = oi_inserted = 0
        for group_key, items in groups.items():
            first = items[0]
            buyer_email = (first["buyer_email"] or "").strip().lower()
            buyer_id = user_map.get(buyer_email)
            if not buyer_id:
                continue

            og_status, _ = map_order_status(
                first.get("payment_status"), first.get("delivery_status")
            )

            # total across all items
            total = sum(
                Decimal(str(i["price"])) * i["quantity"] for i in items
            )

            og_id = uuid.uuid4()
            db.execute(text("""
                INSERT INTO order_groups
                    (id, buyer_id, status, subtotal, delivery_fee, total,
                     delivery_address, created_at)
                VALUES (:id, :buyer, :status, :total, '0.00', :total,
                        cast('{}' as jsonb), :ca)
            """), {
                "id": og_id,
                "buyer": buyer_id,
                "status": og_status,
                "total": str(total),
                "ca": first["order_date"],
            })
            og_inserted += 1

            # sub-group by seller
            by_seller: dict[str, list] = defaultdict(list)
            for item in items:
                se = (item["seller_email"] or "").strip().lower()
                by_seller[se].append(item)

            for seller_email, seller_items in by_seller.items():
                shop_id = email_to_shop.get(seller_email)
                if not shop_id:
                    continue

                _, o_status = map_order_status(
                    seller_items[0].get("payment_status"),
                    seller_items[0].get("delivery_status"),
                )
                o_total = sum(
                    Decimal(str(i["price"])) * i["quantity"] for i in seller_items
                )
                oid = uuid.uuid4()
                db.execute(text("""
                    INSERT INTO orders
                        (id, group_id, shop_id, buyer_id, status,
                         subtotal, delivery_fee, total, created_at, updated_at)
                    VALUES (:id, :og, :shop, :buyer, :status,
                            :sub, '0.00', :sub, :ca, :ca)
                    ON CONFLICT DO NOTHING
                """), {
                    "id": oid,
                    "og": og_id,
                    "shop": shop_id,
                    "buyer": buyer_id,
                    "status": o_status,
                    "sub": str(o_total),
                    "ca": seller_items[0]["order_date"],
                })
                o_inserted += 1

                for item in seller_items:
                    new_pid = product_map.get(item.get("product_id"))
                    unit_price = Decimal(str(item["price"]))
                    qty = item["quantity"]
                    line_total = str(unit_price * qty)
                    snapshot = json.dumps({
                        "name": item["product_name"],
                        "price": str(unit_price),
                    })
                    db.execute(text("""
                        INSERT INTO order_items
                            (id, order_id, product_id, variant_id,
                             product_snapshot, unit_price, quantity, line_total)
                        VALUES (:id, :oid, :pid, NULL,
                                cast(:snap as jsonb), :price, :qty, :line_total)
                        ON CONFLICT DO NOTHING
                    """), {
                        "id": uuid.uuid4(),
                        "oid": oid,
                        "pid": new_pid,
                        "snap": snapshot,
                        "price": str(unit_price),
                        "qty": qty,
                        "line_total": line_total,
                    })
                    oi_inserted += 1

        db.commit()
        log.info(f"  Order groups: {og_inserted}, Orders: {o_inserted}, Items: {oi_inserted}")

        # ── 8. WISHLISTS ──────────────────────────────────────────────────────
        log.info("Migrating wishlists...")
        cur.execute("SELECT * FROM wishlist")
        wl_rows = cur.fetchall()
        inserted = skipped = 0
        for r in wl_rows:
            uid = user_map.get((r["user_email"] or "").strip().lower())
            pid = product_map.get(r["product_id"])
            if not uid or not pid:
                skipped += 1
                continue
            db.execute(text("""
                INSERT INTO wishlists (id, user_id, product_id, added_at)
                VALUES (:id, :uid, :pid, :ca)
                ON CONFLICT (user_id, product_id) DO NOTHING
            """), {
                "id": uuid.uuid4(),
                "uid": uid,
                "pid": pid,
                "ca": r["added_at"],
            })
            inserted += 1

        db.commit()
        log.info(f"  Wishlists: {inserted} inserted, {skipped} skipped")

    my.close()
    log.info("Migration complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Ekshop MySQL → PostgreSQL")
    parser.add_argument("--mysql-host", default="localhost")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-user", required=True)
    parser.add_argument("--mysql-password", required=True)
    parser.add_argument("--mysql-db", required=True)
    parser.add_argument("--postgres-url", required=True,
                        help="e.g. postgresql://user:pass@host/dbname")
    args = parser.parse_args()

    run(
        mysql_cfg={
            "host": args.mysql_host,
            "port": args.mysql_port,
            "user": args.mysql_user,
            "password": args.mysql_password,
            "db": args.mysql_db,
        },
        postgres_url=args.postgres_url,
    )
