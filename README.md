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
├── backend/        FastAPI application
├── frontend/       Next.js application
├── DEVELOPMENT.md  Full architecture decisions and phase roadmap
└── README.md       This file
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
ACCESS_TOKEN_EXPIRE_MINUTES=15
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

This creates all 30 tables in the target database.

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
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Access token TTL (default: 15) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Refresh token TTL (default: 7) |

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

| Tag | Prefix | Status |
|---|---|---|
| Auth | `/auth` | Complete |
| Users | `/users` | In progress |
| Shops | `/shops` | Pending |
| Products | `/products` | Pending |
| Orders | `/orders` | Pending |
| Payments | `/payments` | Pending |
| Delivery | `/delivery` | Pending |
| Recommendations | `/recommendations` | Pending |

Full documentation for the auth system: [`backend/docs/auth_pipeline.md`](backend/docs/auth_pipeline.md)

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

## Contributing

See [`DEVELOPMENT.md`](DEVELOPMENT.md) for the full architecture, all design
decisions made so far, and the implementation roadmap.
