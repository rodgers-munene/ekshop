# Authentication Pipeline

## Overview

Ekshop uses a **stateless JWT + stateful refresh token** hybrid:

- **Access token** — short-lived JWT (15 min). Verified on every protected request
  without a database hit. Contains `user_id` and `role`.
- **Refresh token** — long-lived opaque random string (7 days). Stored in the
  database as a SHA-256 hash, so the raw value is never persisted. Used only to
  obtain a new access token.

This design means routine API calls are fast (no DB lookup per request), while
session revocation is still possible by revoking the refresh token.

---

## Database tables involved

| Table | Purpose |
|---|---|
| `users` | Core identity. `status` controls access (`pending` → `active` → `suspended`). |
| `email_verifications` | One-time tokens for email confirmation and 2FA. |
| `password_resets` | One-time tokens for password recovery (1-hour TTL). |
| `refresh_tokens` | Active sessions. Stores SHA-256 hash of the raw token. |

---

## Security architecture

### Password hashing
- Algorithm: **bcrypt** via the `bcrypt` library.
- A random salt is generated per password — no two hashes are the same even for
  identical passwords.
- The raw password is never stored or logged.

### Access tokens (JWT)
- Algorithm: **HS256** (HMAC-SHA256) signed with `SECRET_KEY` from env.
- Payload: `{ "sub": "<user_uuid>", "role": "<role>", "exp": <timestamp>, "type": "access" }`.
- Verified on every protected request in `app/dependencies/auth.py` without a
  database call.
- TTL: 15 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` in `.env`).

### Refresh tokens
- Generated with `secrets.token_urlsafe(64)` — 512 bits of cryptographic randomness.
- **Only the SHA-256 hash** is stored in `refresh_tokens.token_hash`.
  The raw token is returned to the client once and never stored server-side.
- Looked up by hash: `SELECT * FROM refresh_tokens WHERE token_hash = sha256(raw)`.
  This is O(1) via the unique index and avoids bcrypt's intentional slowness.
- TTL: 7 days (configurable via `REFRESH_TOKEN_EXPIRE_DAYS` in `.env`).
- **Token rotation**: every `/auth/refresh` call revokes the old token and issues
  a new pair. Using the same refresh token twice returns 401.

### Email verification tokens
- Generated with `secrets.token_urlsafe(32)` — URL-safe, unguessable.
- Stored in plain text in `email_verifications.token` (not sensitive — it is a
  one-time activation code sent over email, not a long-lived credential).
- Marked as used immediately on consumption (`used_at` timestamp set).

---

## Full registration pipeline

```
Client                          API                            Database
  |                               |                               |
  |  POST /auth/register          |                               |
  |  { email, password, ...}      |                               |
  |------------------------------>|                               |
  |                               | 1. Normalise email (lowercase)|
  |                               | 2. Check email uniqueness     |
  |                               |------------------------------>|
  |                               |<-- exists? → 400              |
  |                               |                               |
  |                               | 3. Hash password (bcrypt)     |
  |                               | 4. INSERT user (status=pending|
  |                               |------------------------------>|
  |                               | 5. db.flush() → get user.id   |
  |                               |                               |
  |                               | 6. Generate verify token      |
  |                               | 7. INSERT email_verification  |
  |                               |    (expires in 24h)           |
  |                               |------------------------------>|
  |                               | 8. db.commit()                |
  |                               |                               |
  |                               | 9. [TODO] Send email          |
  |                               |    [DEV]  Print token         |
  |                               |                               |
  |<-- 201 { user data }          |                               |
  |    (no tokens yet — account   |                               |
  |     is still pending)         |                               |
```

### What the user receives at this stage
A `201` response with their profile (`UserRead`). They **cannot log in** until
they verify their email. The response deliberately excludes the password hash.

---

## Email verification pipeline

```
Client                          API                            Database
  |                               |                               |
  |  POST /auth/verify-email      |                               |
  |  ?token=<token>               |                               |
  |------------------------------>|                               |
  |                               | 1. Look up token              |
  |                               |    WHERE token = ?            |
  |                               |    AND used_at IS NULL        |
  |                               |------------------------------>|
  |                               |<-- not found → 400            |
  |                               |                               |
  |                               | 2. Check expires_at < now()   |
  |                               |    expired → 400              |
  |                               |                               |
  |                               | 3. UPDATE user SET            |
  |                               |    status = 'active'          |
  |                               | 4. UPDATE verification SET    |
  |                               |    used_at = now()            |
  |                               |------------------------------>|
  |                               | 5. db.commit()                |
  |                               |                               |
  |<-- 200 { "message": "..." }   |                               |
```

After this, the account is `active` and login is possible.

---

## Login pipeline

```
Client                          API                            Database
  |                               |                               |
  |  POST /auth/login             |                               |
  |  { email, password }          |                               |
  |------------------------------>|                               |
  |                               | 1. Normalise email            |
  |                               | 2. SELECT user WHERE          |
  |                               |    email = ?                  |
  |                               |------------------------------>|
  |                               |<-- not found OR               |
  |                               |    bcrypt.verify() fails      |
  |                               |    → 401 (same message for    |
  |                               |    both, prevents enumeration)|
  |                               |                               |
  |                               | 3. Check status:              |
  |                               |    pending   → 403            |
  |                               |    suspended → 403            |
  |                               |                               |
  |                               | 4. Create JWT access token    |
  |                               |    payload: sub, role, exp    |
  |                               |    signed with SECRET_KEY     |
  |                               |                               |
  |                               | 5. Generate refresh token     |
  |                               |    (64-byte random string)    |
  |                               | 6. INSERT refresh_token       |
  |                               |    token_hash = sha256(raw)   |
  |                               |------------------------------>|
  |                               |                               |
  |                               | 7. UPDATE user                |
  |                               |    last_login_at = now()      |
  |                               |------------------------------>|
  |                               | 8. db.commit()                |
  |                               |                               |
  |<-- 200 {                      |                               |
  |     access_token,             |                               |
  |     refresh_token,            |                               |
  |     token_type: "bearer"      |                               |
  |   }                           |                               |
```

---

## Token refresh pipeline

```
Client                          API                            Database
  |                               |                               |
  |  POST /auth/refresh           |                               |
  |  ?raw_token=<refresh_token>   |                               |
  |------------------------------>|                               |
  |                               | 1. sha256(raw_token)          |
  |                               | 2. SELECT refresh_token       |
  |                               |    WHERE token_hash = ?       |
  |                               |    AND revoked_at IS NULL     |
  |                               |------------------------------>|
  |                               |<-- not found → 401            |
  |                               |                               |
  |                               | 3. Check expires_at < now()   |
  |                               |    expired → 401              |
  |                               |                               |
  |                               | 4. Revoke old token           |
  |                               |    SET revoked_at = now()     |
  |                               | 5. Issue new access token     |
  |                               | 6. Issue new refresh token    |
  |                               |    INSERT refresh_token       |
  |                               |------------------------------>|
  |                               | 7. db.commit()                |
  |                               |                               |
  |<-- 200 { new token pair }     |                               |
```

**Token rotation** means if an attacker steals a refresh token and uses it
after the legitimate client has already rotated it, they get 401. The legitimate
client's next request will also fail, alerting them that their session was
compromised.

---

## Logout pipeline

```
Client                          API                            Database
  |                               |                               |
  |  POST /auth/logout            |                               |
  |  Authorization: Bearer <AT>   |                               |
  |  ?raw_token=<refresh_token>   |                               |
  |------------------------------>|                               |
  |                               | 1. Validate access token      |
  |                               |    (proves caller owns session|
  |                               |     being terminated)         |
  |                               |                               |
  |                               | 2. sha256(raw_token)          |
  |                               | 3. Revoke refresh token       |
  |                               |    SET revoked_at = now()     |
  |                               |------------------------------>|
  |                               | 4. db.commit()                |
  |                               |                               |
  |<-- 200 { "message": "..." }   |                               |
  |                               |                               |
  |  Client discards both tokens  |                               |
```

The access token is **not** server-side revoked — it expires naturally after
its TTL (15 min). The client must discard it immediately on logout.

---

## Password reset pipeline

```
Step 1 — Request reset
  POST /auth/forgot-password?email=...
  → Always returns 200 (same message whether email exists or not)
  → If user exists: generates token, stores in password_resets (1h TTL)
  → [TODO] Sends email with reset link

Step 2 — Set new password
  POST /auth/reset-password?token=...&new_password=...
  → Validates token (unused, not expired)
  → Hashes new password, updates user record
  → Marks reset token as used
  → Revokes ALL active refresh tokens for this user
     (forces re-login on all devices)
```

---

## Protected request flow (every API call after login)

```
Client                          API (dependencies/auth.py)
  |                               |
  |  GET /some/protected/route    |
  |  Authorization: Bearer <JWT>  |
  |------------------------------>|
  |                               | 1. Extract token from header
  |                               | 2. jwt.decode(token, SECRET_KEY)
  |                               |    invalid signature → 401
  |                               |    expired → 401
  |                               |    wrong type → 401
  |                               |
  |                               | 3. Extract sub (user UUID)
  |                               | 4. SELECT user WHERE id = sub
  |                               |    not found → 401
  |                               |
  |                               | 5. Role check (if route requires it):
  |                               |    require_seller → role != seller → 403
  |                               |    require_admin  → role != admin  → 403
  |                               |
  |                               | 6. Inject user into route handler
  |<-- route response             |
```

---

## Auth dependency hierarchy

```
get_current_user          → validates JWT, fetches user from DB
    └── get_current_active_user  → + checks status == active
            ├── require_seller   → + checks role == seller
            └── require_admin    → + checks role == admin
```

Usage in any router:
```python
from app.dependencies.auth import get_current_active_user, require_seller

@router.get("/me")
def get_me(user: User = Depends(get_current_active_user)):
    ...

@router.post("/products")
def create_product(user: User = Depends(require_seller)):
    ...
```

---

## Error reference

| Endpoint | Code | Reason |
|---|---|---|
| `/register` | 400 | Email already registered |
| `/verify-email` | 400 | Token not found, already used, or expired |
| `/login` | 401 | Wrong email or password |
| `/login` | 403 | Account pending (unverified) or suspended |
| `/refresh` | 401 | Token not found, revoked, or expired |
| `/logout` | 401 | Missing or invalid access token in header |
| `/reset-password` | 400 | Token not found, already used, or expired |
| Any protected route | 401 | Missing, invalid, or expired access token |
| Any protected route | 403 | Correct token but wrong role or inactive account |

---

## What is not yet implemented (TODOs)

| Feature | Location | Notes |
|---|---|---|
| Send verification email | `routers/auth.py:register` | Token is printed to terminal in dev |
| Send password reset email | `routers/auth.py:forgot_password` | Token is printed to terminal in dev |
| Resend verification email | Not built | Needed if token expires before user verifies |
| 2FA (TOTP/OTP) | `models/user.py:EmailVerification` | `purpose=two_factor` is modelled, not wired |
| IP logging on login | `models/user.py:last_login_ip` | Column exists, not populated yet |
| Rate limiting on login | `main.py` | Prevent brute-force — add `slowapi` middleware |
