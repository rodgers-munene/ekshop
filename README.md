# Ekshop

A multi-vendor e-commerce marketplace for Kenya. Sellers set up shops and list
products. Buyers browse, search, and purchase. The platform handles delivery
coordination, payment processing (Paystack + M-Pesa), and uses personalised
recommendation algorithms to surface relevant products to each user.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.137 (Python 3.12) |
| Database | PostgreSQL via Supabase |
| ORM & migrations | SQLAlchemy 2 + Alembic |
| Frontend | Next.js 16 + React 19 (TypeScript) |
| Styling | Tailwind CSS v4 |
| Auth | JWT (python-jose) + bcrypt |

---

## Prerequisites

Make sure the following are installed before you begin:

- **Python** 3.12+
- **Node.js** 20+ and **npm** 11+
- **PostgreSQL** 16+ (local) — or a [Supabase](https://supabase.com) project
- **Git**

---

## Repository structure

```
ekshop/
├── backend/            FastAPI application
├── frontend/           Next.js application
├── infra/terraform/    AWS infrastructure (EC2, ECR, IAM/OIDC, S3, Secrets Manager)
├── .github/workflows/  CI/CD — migrate + build + deploy to AWS on push to main
├── DEVELOPMENT.md      Full architecture decisions and phase roadmap
└── README.md           This file
```

---

## Backend setup

### 1. Create and activate a virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the values:

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/dbname
SECRET_KEY=<generate below>
ACCESS_TOKEN_EXPIRE_DAYS=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

Generate a secure `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Supabase users:** The direct connection (`db.xxx.supabase.co:5432`) may only
> resolve to an IPv6 address on some networks. If you get "Network is unreachable",
> use the **Session Pooler** URL instead. Find it in your Supabase project under
> **Project Settings → Database → Connection pooling → Session pooler**.
> Prefix the URL with `postgresql+psycopg://`.

### 4. Run database migrations

```bash
alembic upgrade head
```

This creates all tables in the target database (see [`backend/docs/architecture_overview.pdf`](backend/docs/architecture_overview.pdf) for the full data model).

### 5. Start the development server

```bash
uvicorn app.main:app --reload
```

The API is now running at **http://localhost:8000**

Interactive API docs (Swagger UI): **http://localhost:8000/docs**

---

## Frontend setup

### 1. Install dependencies

```bash
cd frontend
npm install
```

### 2. Configure environment variables

```bash
cp .env.example .env.local     # if .env.example exists, otherwise create .env.local
```

Add the backend URL:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start the development server

```bash
npm run dev
```

The app is now running at **http://localhost:3000**

---

## Running both servers together

Open two terminal tabs:

```bash
# Terminal 1 — backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

---

## Environment variable reference

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string (`postgresql+psycopg://...`) |
| `SECRET_KEY` | Yes | JWT signing secret — must be random and kept private |
| `ACCESS_TOKEN_EXPIRE_DAYS` | No | Access token TTL in days (default: 15) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Refresh token TTL in days (default: 7) |
| `CORS_ORIGINS` | Yes | Comma-separated list of allowed frontend origins |
| `PAYSTACK_SECRET_KEY` / `PAYSTACK_PUBLIC_KEY` | Yes | Live payment provider |
| `MPESA_*` (consumer key/secret, shortcode, passkey, environment, callback URL) | No | M-Pesa Daraja STK Push — built but not linked into checkout until the Daraja app is approved for production |
| `RESEND_API_KEY` / `EMAIL_FROM` | No | Transactional email; falls back to console logging in dev |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_REGION` / `AWS_S3_BUCKET` / `AWS_S3_PUBLIC_URL` | No | Product/hero image storage; uploads fail with a 502 until these are set |

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Yes | Backend base URL (e.g. `http://localhost:8000`) |

---

## Database migrations

All migrations live in `backend/alembic/versions/`.

```bash
# Apply all pending migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Generate a new migration after changing a model
alembic revision --autogenerate -m "describe_your_change"

# View migration history
alembic history
```

> The database URL is read from `DATABASE_URL` in `.env`. The value in
> `alembic.ini` is intentionally left blank.

---

## API overview

| Tag | Prefix | Handles |
|---|---|---|
| Auth | `/auth` | Register, verify, login, refresh, logout, password reset |
| Users | `/users` | Profile, addresses, wishlist, notification preferences |
| Shops | `/shops` | Shop CRUD, public storefront, seller dashboard |
| Categories / Products | `/categories`, `/products` | Catalog browsing, full-text search, product detail |
| Cart / Checkout | `/cart`, `/checkout` | Cart CRUD, multi-vendor order splitting, delivery-fee preview |
| Orders | `/orders` | Buyer order history and detail |
| Payments | `/payments` | Paystack (live) + M-Pesa (built, not yet linked) init/callback/verify, stuck-payment reconciliation |
| Delivery | `/delivery` | Agent auth, assignment, tracking, admin-configurable delivery rates |
| Admin | `/admin` | User/shop moderation, platform operations |
| Messaging, Recommendations, Hero, Deals, Notifications | — | Buyer↔shop chat, personalization, homepage merchandising |

Every router above is implemented and mounted in `app/main.py` — see [`backend/docs/architecture_overview.pdf`](backend/docs/architecture_overview.pdf) for the full architecture, including data model, auth flow, payments, delivery pricing, frontend structure, and deployment infrastructure.

Full documentation for the auth system: [`backend/docs/auth_pipeline.md`](backend/docs/auth_pipeline.md) *(note: this doc's stated token TTL and rate-limiting status have drifted from the code — see the architecture PDF for the current state)*

Full development roadmap: [`DEVELOPMENT.md`](DEVELOPMENT.md)

---

## Development notes

- In development, email verification tokens and password reset tokens are
  **printed to the terminal** instead of being sent by email. Look for lines
  starting with `[DEV]` in the server output.

- The `backend/venv/` directory and `backend/.env` file are gitignored.
  Never commit real credentials.

- Money values in the database are stored as strings (e.g. `"1250.00"`) to
  avoid float precision issues. They are parsed to `Decimal` in the service
  layer when arithmetic is needed.

---

## Deployment & architecture

- **Backend**: containerized (`backend/Dockerfile`), pushed to AWS ECR, and deployed to a single EC2 instance via GitHub Actions using OIDC (no long-lived AWS keys) and SSM Run Command (no SSH). Infrastructure is defined in [`infra/terraform/`](infra/terraform/README.md). Every push to `main` touching `backend/**` runs Alembic migrations in CI before the new image is deployed.
- **Frontend**: standard Next.js app deployed on Vercel via its own git integration — no custom pipeline in this repo.
- **Database**: managed PostgreSQL on Supabase.

For the full picture — data model, auth, payments, delivery pricing, frontend structure, CI/CD, and AWS resources — see [`backend/docs/architecture_overview.pdf`](backend/docs/architecture_overview.pdf).

---

## Contributing

See [`DEVELOPMENT.md`](DEVELOPMENT.md) for the full architecture, all design
decisions made so far, and the implementation roadmap.
