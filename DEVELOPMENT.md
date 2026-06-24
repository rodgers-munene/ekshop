# Ekshop — Development Log

## What is Ekshop

A multi-vendor e-commerce marketplace for Kenya. Sellers register, set up a shop,
and list products. Buyers browse, search, and purchase. The platform handles
delivery coordination, payment processing (Paystack + M-Pesa), and uses
personalised recommendation algorithms to surface relevant products to each user.

---

## Why We Rewrote It

The original system was PHP + MySQL (MariaDB) hosted on cPanel. It worked but had
accumulated serious architectural problems that made it unscalable:

### Problems in the old codebase

**Database antipatterns**
- One table per product category (`clothing`, `electronics`, `home_essentials`,
  `nicotine`). Adding a new category required creating a new database table.
- `cart` and `wishlist` stored `product_name`, `image_path`, `price` directly.
  Stale data was guaranteed whenever a seller updated a product.
- No proper order line items. `order_summary` had one row per product ordered,
  not one row per order. Aggregating an order required `GROUP BY order_group_id`.
- Email as primary key on `users`. Expensive joins everywhere and impossible to
  let users change their email.
- Four overlapping auth token tables (`user_authentication`, `user_verification`,
  `two_factor_auth1`, `password_reset`) doing variations of the same thing.
- Mixed storage engines: some tables were MyISAM (no FK constraints, no
  transactions), others InnoDB.
- Backup tables polluting the schema (`cart_backup_20251005_051125`, etc.).

**Custom "AI" tables**
The system had 11 `ai_*` tables implementing a homebuilt intelligence system that
scanned the database on a cron job and stored observations as text rows. This was
replaced with a proper recommendation data model (`user_events`, `product_scores`,
`user_preferences`).

**No separation of concerns**
PHP files mixed SQL queries, business logic, HTML rendering, and session handling
in the same file.

### What we chose instead

| Layer | Old | New | Reason |
|---|---|---|---|
| Backend | PHP 8.4 | FastAPI (Python) | Async support, auto-generated API docs, type safety, better ecosystem for ML/recommendations |
| Database | MariaDB (MySQL) | PostgreSQL (Supabase) | JSONB, ARRAY types, UUID support, better for analytics queries, managed hosting |
| Frontend | HTML + JS + CSS | Next.js 16 (TypeScript) | React Server Components, SSR/SSG for SEO, App Router, type safety |
| ORM | Raw SQL / PDO | SQLAlchemy 2 + Alembic | Migration management, relationship loading, Pythonic queries |
| Auth | PHP sessions | JWT + refresh tokens | Stateless, works across mobile/web, revocable sessions |
| Styling | Raw CSS | Tailwind CSS v4 | Utility-first, no CSS files to maintain |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Client (Browser / Mobile)                              │
│  Next.js 16 — TypeScript — Tailwind CSS                 │
│  App Router: RSC for pages, client components for UI    │
└───────────────┬─────────────────────────────────────────┘
                │  HTTPS / REST
                ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI (Python)                                       │
│  Routers → Services → Models → Database                 │
│  JWT auth, Pydantic validation, SQLAlchemy ORM          │
└───────────────┬─────────────────────────────────────────┘
                │  psycopg (v3)
                ▼
┌─────────────────────────────────────────────────────────┐
│  PostgreSQL (Supabase)                                  │
│  Production DB — managed, with Storage for media        │
└─────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
ekshop/
├── backend/                    FastAPI application
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py       Environment variables
│   │   │   ├── database.py     SQLAlchemy engine + session
│   │   │   └── security.py     Hashing, JWT, token generation
│   │   ├── dependencies/
│   │   │   ├── auth.py         get_current_user, require_seller, require_admin
│   │   │   └── database.py     get_db session dependency
│   │   ├── models/             SQLAlchemy ORM models (one file per domain)
│   │   │   ├── __init__.py     Imports all models (required by Alembic)
│   │   │   ├── user.py         User, EmailVerification, PasswordReset, RefreshToken
│   │   │   ├── shop.py         Shop, ShopPaymentMethod
│   │   │   ├── catalog.py      Category, Product, ProductImage, ProductVariant, ProductReview
│   │   │   ├── commerce.py     UserAddress, Cart, CartItem, Wishlist, OrderGroup, Order, OrderItem
│   │   │   ├── payment.py      Payment, PaymentIntent
│   │   │   ├── delivery.py     DeliveryAgent, Delivery, DeliveryEvent, Notification
│   │   │   ├── subscription.py SubscriptionPlan, Subscription
│   │   │   ├── messaging.py    Conversation, Message
│   │   │   └── analytics.py    UserEvent, ProductScore, UserPreference, SearchTerm, ...
│   │   ├── routers/            FastAPI route handlers
│   │   │   ├── auth.py         ✅ Registration, login, logout, token refresh, password reset
│   │   │   ├── users.py        🔲 Profile, addresses, notifications
│   │   │   ├── products.py     🔲 Product CRUD, images, variants
│   │   │   ├── orders.py       🔲 Cart, checkout, order management
│   │   │   ├── payment.py      🔲 Paystack, M-Pesa integration
│   │   │   ├── delivery.py     🔲 Delivery agent assignment, tracking
│   │   │   └── ai.py           🔲 Recommendations, personalised feed
│   │   ├── schemas/            Pydantic request/response models
│   │   │   ├── user.py         ✅ UserCreate, UserRead, TokenResponse, LoginRequest
│   │   │   ├── shop.py         ✅ ShopCreate, ShopRead, ShopUpdate
│   │   │   ├── catalog.py      ✅ ProductCreate, ProductRead, ReviewCreate, ...
│   │   │   ├── commerce.py     ✅ CartRead, OrderRead, UserAddressCreate, ...
│   │   │   ├── payment.py      ✅ PaymentInitiate, PaymentRead
│   │   │   ├── delivery.py     ✅ DeliveryRead
│   │   │   └── messaging.py    ✅ ConversationRead, MessageCreate, MessageRead
│   │   ├── services/           Business logic (to be filled as routers are implemented)
│   │   │   ├── auth_service.py 🔲
│   │   │   ├── product_service.py 🔲
│   │   │   ├── order_service.py   🔲
│   │   │   └── payment_service.py 🔲
│   │   └── main.py             FastAPI app, CORS, router registration
│   ├── alembic/                Database migration management
│   │   ├── env.py
│   │   └── versions/           Generated migration files
│   ├── docs/
│   │   └── auth_pipeline.md    ✅ Full auth system documentation
│   ├── .env                    DATABASE_URL, SECRET_KEY, token TTLs
│   └── requirements.txt
│
└── frontend/                   Next.js 16 application
    ├── app/                    App Router pages
    │   ├── layout.tsx          Root layout
    │   ├── page.tsx            Homepage (to be built)
    │   └── globals.css         Tailwind base styles
    └── package.json
```

---

## Development Phases

### Phase 1 — Database Design & Models ✅

**Goal:** Replace the messy multi-table MySQL schema with a clean, normalised
PostgreSQL schema. Write all SQLAlchemy ORM models and Pydantic schemas.

**Key decisions made:**

- Switched from email as primary key to `UUID` on all tables. Faster joins,
  no updates needed if a user changes email, no sequential ID guessing.

- All money values stored as `String(20)` (e.g. `"1250.00"`) rather than
  `DECIMAL`. Avoids Python float-to-decimal conversion bugs at the ORM layer.
  Will be parsed to `Decimal` in the service layer when doing arithmetic.

- `user_events` uses `BigInteger` autoincrement PK instead of UUID. This table
  will receive millions of inserts (every page view, click, search). Sequential
  integers are faster to insert and index than UUIDs for high-volume append-only
  tables.

- All enums use `native_enum=False` (stored as VARCHAR). PostgreSQL native enums
  are hard to alter — you must drop and recreate the type to add a value. VARCHAR
  enums can be extended in a simple migration.

- `product_snapshot JSONB` on `order_items`. Stores a copy of the product name,
  price, and image at the time of purchase. Means order history is always accurate
  even if the seller later edits or deletes the product.

- `delivery_address JSONB` on `order_groups`. Same reasoning — the address used
  for an order must never change retroactively even if the user updates their
  saved address.

**Tables created (30 total):**

| Domain | Tables |
|---|---|
| Identity & Auth | `users`, `email_verifications`, `password_resets`, `refresh_tokens`, `notification_preferences` |
| Shops | `shops`, `shop_payment_methods` |
| Catalog | `categories`, `products`, `product_images`, `product_variants`, `product_reviews` |
| Commerce | `user_addresses`, `carts`, `cart_items`, `wishlists`, `order_groups`, `orders`, `order_items` |
| Payments | `payments`, `payment_intents` |
| Delivery | `delivery_agents`, `deliveries`, `delivery_events`, `notifications` |
| Subscriptions | `subscription_plans`, `subscriptions` |
| Messaging | `conversations`, `messages` |
| Analytics | `user_events`, `product_scores`, `user_preferences`, `search_terms`, `hero_slides`, `promotions`, `weekly_analytics`, `issue_reports`, `product_requests` |

**Migration:** Run with Alembic against Supabase PostgreSQL via Session Pooler
(IPv4, port 5432). Direct connection (`db.xxx.supabase.co`) only resolves to IPv6
on this network.

---

### Phase 2 — Authentication System ✅

**Goal:** Implement full auth: registration, email verification, login, token
refresh, logout, and password reset.

**Documentation:** See [backend/docs/auth_pipeline.md](backend/docs/auth_pipeline.md)
for full pipeline diagrams and security architecture.

**Key decisions made:**

- Dropped `passlib` in favour of the `bcrypt` library directly. Passlib has not
  been maintained since 2020 and throws `ValueError` with bcrypt v4.x due to a
  strict 72-byte password length check introduced in the newer library.

- Refresh tokens are never stored raw. The client receives the random string;
  the database stores only `sha256(token)`. Lookup by hash is O(1) via the unique
  index and does not require bcrypt's intentional slowness.

- Token rotation on every refresh. Each refresh token is single-use. The old one
  is revoked atomically before the new pair is issued. If a stolen token is used
  after the legitimate client has rotated, the attacker gets 401 and the
  legitimate client's next call also fails — signalling a compromise.

- `forgot-password` always returns `200` with the same message. Prevents user
  enumeration (attacker cannot determine if an email is registered).

- On password reset, all active refresh tokens for the user are revoked. Forces
  re-login on all devices — standard practice after a credential change.

**Endpoints implemented:**

| Method | Path | Auth required | Description |
|---|---|---|---|
| POST | `/auth/register` | No | Create account, send verification email |
| POST | `/auth/verify-email` | No | Activate account with email token |
| POST | `/auth/login` | No | Get access + refresh token pair |
| POST | `/auth/refresh` | No | Rotate tokens |
| POST | `/auth/logout` | Yes (Bearer) | Revoke refresh token |
| POST | `/auth/forgot-password` | No | Request password reset link |
| POST | `/auth/reset-password` | No | Set new password, revoke all sessions |

**Auth dependency hierarchy:**
```
get_current_user
    └── get_current_active_user
            ├── require_seller
            └── require_admin
```

---

### Phase 3 — Users & Shops 🔲

**Goal:** User profile management and seller shop setup.

**Endpoints to build:**

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/users/me` | Active user | Get own profile |
| PATCH | `/users/me` | Active user | Update profile |
| GET | `/users/me/addresses` | Active user | List saved addresses |
| POST | `/users/me/addresses` | Active user | Add address |
| PATCH | `/users/me/addresses/{id}` | Active user | Update address |
| DELETE | `/users/me/addresses/{id}` | Active user | Delete address |
| GET | `/users/me/notifications` | Active user | Get notifications (paginated) |
| PATCH | `/users/me/notifications/{id}/read` | Active user | Mark as read |
| POST | `/shops` | Seller | Create shop |
| GET | `/shops/{slug}` | Public | View shop storefront |
| PATCH | `/shops/me` | Seller | Update own shop |
| POST | `/shops/me/payment-methods` | Seller | Add payment method |
| GET | `/shops/me/dashboard` | Seller | Revenue, orders, top products |

---

### Phase 4 — Catalog 🔲

**Goal:** Category tree, product CRUD, image upload, variants, reviews.

**Endpoints to build:**

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/categories` | Public | Full category tree |
| GET | `/categories/{slug}/products` | Public | Products in category |
| GET | `/products` | Public | Paginated product listing with filters |
| GET | `/products/{slug}` | Public | Single product detail |
| POST | `/products` | Seller | Create product |
| PATCH | `/products/{id}` | Seller (owner) | Update product |
| DELETE | `/products/{id}` | Seller (owner) | Delete product |
| POST | `/products/{id}/images` | Seller (owner) | Upload image to Supabase Storage |
| DELETE | `/products/{id}/images/{img_id}` | Seller (owner) | Remove image |
| POST | `/products/{id}/reviews` | Buyer (verified purchase) | Leave review |
| GET | `/products/{id}/reviews` | Public | Paginated reviews |

**Filters for GET /products:**
`?category=&min_price=&max_price=&county=&condition=&status=&sort=trending|newest|price_asc|price_desc&q=`

---

### Phase 5 — Commerce (Cart, Checkout, Orders) 🔲

**Goal:** Cart management, multi-seller checkout, order lifecycle.

**Key design note:** One checkout can span multiple sellers. The `order_groups`
table groups all orders from a single checkout. Each `orders` row belongs to one
shop. `order_items` are the line items within each shop's order.

**Endpoints to build:**

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/cart` | Active user | Get cart with items |
| POST | `/cart/items` | Active user | Add item to cart |
| PATCH | `/cart/items/{id}` | Active user | Change quantity |
| DELETE | `/cart/items/{id}` | Active user | Remove item |
| DELETE | `/cart` | Active user | Clear cart |
| GET | `/wishlist` | Active user | Get wishlist |
| POST | `/wishlist` | Active user | Add to wishlist |
| DELETE | `/wishlist/{product_id}` | Active user | Remove from wishlist |
| POST | `/checkout` | Active user | Create order group from cart |
| GET | `/orders` | Active user | List own orders |
| GET | `/orders/{id}` | Active user | Order detail |
| PATCH | `/orders/{id}/cancel` | Buyer | Cancel order |
| GET | `/seller/orders` | Seller | Incoming orders for own shop |
| PATCH | `/seller/orders/{id}/confirm` | Seller | Confirm order |

---

### Phase 6 — Payments 🔲

**Goal:** Integrate Paystack for card payments and M-Pesa STK push.

**Flow:**
1. `POST /payments/initiate` — create a `payment_intents` record, get Paystack
   reference, redirect client to Paystack checkout or trigger STK push.
2. Paystack webhook `POST /payments/paystack/callback` — verify signature,
   update `payments` record to `success`, trigger order group status update.
3. M-Pesa callback `POST /payments/mpesa/callback` — same pattern.

**Key decisions to make:**
- Idempotent webhook handling (replay protection).
- Partial payment handling if a seller cancels one item in a multi-seller order.

---

### Phase 7 — Delivery 🔲

**Goal:** Delivery agent assignment, status tracking, customer notifications.

**Flow:**
1. Order confirmed → `deliveries` record created with status `pending`.
2. Admin or system assigns a delivery agent → status `assigned`.
3. Agent app (or admin panel) updates to `picked`, `in_transit`, `delivered`.
4. Each status change writes a row to `delivery_events` and pushes a
   `notifications` entry to the buyer.

---

### Phase 8 — Recommendations & Product Amplification 🔲

**Goal:** Personalised homepage feed, "Similar products", trending rankings.

**Data foundation (already modelled):**
- `user_events` — every view, click, cart add, purchase, search fired from client.
- `product_scores` — rolling 7-day aggregates recomputed by a background job.
- `user_preferences` — per-user category weights and price ranges, updated from
  purchase and event history.

**Algorithms to implement:**

*Trending score (cold start / anonymous users):*
```
trending_score =
  (views_7d × 0.2) +
  (clicks_7d × 0.3) +
  (carts_7d  × 0.4) +
  (purchases_7d × 0.8) +
  (wishlists_7d × 0.3)
  × recency_decay
  × quality_factor
```
`quality_factor = seller_rating × stock_available × image_count × review_score`

*Content-based filtering (returning users):*
- Build a category weight vector per user from `user_preferences.category_weights`.
- Score candidate products by overlap with the weight vector.
- Boost products in the user's `preferred_counties`.

*Collaborative filtering (returning users with purchase history):*
- "Users who bought X also bought Y" — item-item similarity via `order_items`
  co-occurrence. Start with SQL window functions, upgrade to `pgvector` cosine
  similarity when data volume justifies it.

*Endpoints to build:*

| Method | Path | Description |
|---|---|---|
| GET | `/recommendations/feed` | Personalised homepage products |
| GET | `/recommendations/similar/{product_id}` | Similar products |
| GET | `/recommendations/trending` | Platform-wide trending |
| POST | `/events` | Ingest a single user event from frontend |

---

### Phase 9 — Frontend (Next.js) 🔲

**Goal:** Build all pages and connect to the FastAPI backend.

**Architecture decisions:**
- Use React Server Components (RSC) for pages that only display data (product
  listings, product detail, shop pages). Faster, better SEO, no client JS bundle.
- Use Client Components for interactive parts: cart drawer, auth forms,
  checkout flow, real-time messaging.
- State: Zustand for cart + auth state (lightweight, no boilerplate).
- Data fetching: TanStack Query for client-side with caching and background refetch.
- API client: a typed `fetch` wrapper at `lib/api.ts` that attaches JWT tokens.
- UI components: shadcn/ui (Radix + Tailwind).

**Pages to build:**

```
Public
  /                           Personalised feed (trending if anonymous)
  /search                     Search results with filter sidebar
  /categories/[slug]          Category product grid
  /products/[slug]            Product detail, images, variants, reviews
  /shops/[slug]               Seller storefront

Auth
  /login
  /register                   Step 1: choose buyer or seller
  /verify-email

Buyer
  /cart
  /checkout
  /orders
  /orders/[id]
  /wishlist
  /profile

Seller
  /seller/dashboard           Revenue, orders, top products
  /seller/shop/setup          First-time shop creation wizard
  /seller/shop/edit
  /seller/products            Product list with status management
  /seller/products/new
  /seller/products/[id]/edit
  /seller/orders              Incoming orders

Admin
  /admin/dashboard
  /admin/users
  /admin/sellers              Verify / suspend sellers
  /admin/categories
```

---

## Environment Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env with:
# DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:<port>/<db>
# SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
# ACCESS_TOKEN_EXPIRE_MINUTES=15
# REFRESH_TOKEN_EXPIRE_DAYS=7

alembic upgrade head
uvicorn app.main:app --reload
# API docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# App at http://localhost:3000
```

### Database note

Supabase `db.xxx.supabase.co:5432` resolves to IPv6 only on some networks.
Use the **Session Pooler** URL from Supabase Project Settings → Database →
Connection Pooling if direct connection fails with "Network is unreachable".

---

## Key Technical Decisions Log

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Password hashing | `bcrypt` (direct) | `passlib[bcrypt]` | passlib unmaintained, breaks with bcrypt v4.x |
| JWT library | `python-jose` | `PyJWT` | FastAPI ecosystem convention, simpler API |
| Refresh token storage | SHA-256 hash in DB | bcrypt hash in DB | SHA-256 is fast — allows direct DB lookup by hash. bcrypt is intentionally slow, scanning all tokens would be O(n × bcrypt_cost) |
| Money representation | `String("1250.00")` | `DECIMAL(12,2)` | Avoids ORM float conversion bugs. Parsed to `Decimal` in service layer |
| Enum storage | `VARCHAR` (`native_enum=False`) | PostgreSQL native ENUM | Native enums require DDL changes to add values; VARCHAR only needs a migration comment |
| Event table PK | `BigInteger` autoincrement | `UUID` | High-volume append-only table. Sequential integers insert faster and produce smaller indexes |
| Product history in orders | `product_snapshot JSONB` | FK to products only | Sellers can edit/delete products. Snapshot preserves the state at purchase time |

---

## Current Status

| Phase | Status | Notes |
|---|---|---|
| 1 — Database & Models | ✅ Complete | 30 tables, all models and schemas written |
| 2 — Authentication | ✅ Complete | All 7 endpoints working, documented |
| 3 — Users & Shops | 🔲 Next | Start with `/users/me` and `POST /shops` |
| 4 — Catalog | 🔲 Pending | Depends on shops |
| 5 — Commerce | 🔲 Pending | Depends on catalog |
| 6 — Payments | 🔲 Pending | Depends on commerce |
| 7 — Delivery | 🔲 Pending | Depends on orders |
| 8 — Recommendations | 🔲 Pending | Depends on user events (Phase 4+) |
| 9 — Frontend | 🔲 Pending | Can start auth pages now |
