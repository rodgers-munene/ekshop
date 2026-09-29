# Delivery, Fleet & Rider Payouts

## Overview

Rider deliveries are managed by four cooperating subsystems, all living behind
the `/delivery` and `/payments` routers with the domain logic concentrated in
`app/services/fleet.py`:

1. **Rider onboarding & KYC gating** — nobody is dispatchable until an admin
   approves their KYC and verifies their equipment.
2. **Ping dispatch engine** — nearby riders are offered a delivery one at a
   time with a 30-second countdown; when the order is paid, dispatch runs
   automatically.
3. **Wallet ledger & B2C payouts** — every money movement is a timestamped
   ledger row with a running balance; M-Pesa B2C disbursements reconcile
   against Daraja's Result callback, not against the initiation response.
4. **Metered pricing & surge** — distance-based fees per vehicle multiplied by
   peak-hours, rain (OpenWeather) and supply/demand surge, capped.

There are **no background workers**: ping expiry is lazy (computed on read),
and nothing in the payout path races a scheduler.

---

## Configuration

All values are set in `app/core/config.py` / `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `PING_RADIUS_KM` | `5.0` | Search radius around the pickup point for eligible riders. |
| `PING_EXPIRY_SECONDS` | `30` | How long an individual rider has to accept before the next is promoted. |
| `RIDER_PAYOUT_SHARE` | `0.80` | Share of the delivery fee credited to the rider on completion (80/20). |
| `MPESA_B2C_INITIATOR_NAME` | — | B2C initiator name from the Daraja portal (must be a utility/storage shortcode). |
| `MPESA_B2C_SECURITY_CREDENTIAL` | — | The base64-encrypted initiator password — the only payout secret the API reads. |
| `MPESA_B2C_SHORTCODE` | — | B2C `PartyA`. Falls back to `MPESA_SHORTCODE`. |
| `MPESA_RESULT_URL` / `MPESA_TIMEOUT_URL` | — | Callback URLs registered in the Daraja portal. When unset, the app signs its own fallback URLs. |
| `MPESA_CALLBACK_URL` / `MPESA_CALLBACK_SECRET` | — | Base for fallback Result/Timeout URLs; the secret signs them with `?token=`. |
| `OPENWEATHER_API_KEY` | — | Enables real-time rain surge lookups. Unset ⇒ weather surge disabled. |
| `ORS_API_KEY` / `ORS_BASE_URL` | — | Distance/time provider for quotes (also used by the legacy delivery-fee path). |

> **Important (B2C shortcode):** Daraja does not support B2C on buy-goods tills.
> `PartyA` for B2C must be a utility/storage M-Pesa shortcode.

---

## Database tables

| Table | Purpose |
|---|---|
| `delivery_agents` | Riders. `kyc_status`, `equipment_verified`, `status`, `current_order_id`, `current_lat/lng`, `wallet_balance`. |
| `deliveries` | One row per order needing a rider: `tracking_number` (`EKS-` + 8 hex), status, agent, timestamps. |
| `delivery_offers` | The ping itself. `status` (`pending`/`queued`/`accepted`/`declined`/`expired`/`cancelled`), `queue_position`, `expires_at`. |
| `delivery_ledger_entries` | Double-entry-style wallet rows with `balance_after` stamped on every row. |
| `delivery_pricing_rules` | Per-vehicle metered rate + surge multipliers. |
| `delivery_events` | Audit trail of status changes (actor + notes). |

All wallet writes funnel through `fleet.post_ledger_entry()`, so no code path
can mutate a balance without a matching ledger row.

---

## 1. Rider onboarding & KYC gating

- A rider signs up via `POST /delivery/auth/login` / the rider PWA and is
  created **inactive**.
- `PUT /delivery/kyc/me` submits identity (vehicle type, national ID, licence,
  documents, equipment photo). Status becomes `pending_review`.
- Only `GET /delivery/admin/kyc` (the admin **Rider KYC** page) can move a
  submission forward:
  - `POST /delivery/admin/kyc/{agent_id}/approve` → `approved` and sets
    `equipment_verified=True`.
  - `POST /delivery/admin/kyc/{agent_id}/reject` → `rejected`, sets
    `equipment_verified=False` and deactivates the agent.
- `fleet.eligible_for_pings()` is the **only** gate the dispatch engine uses:
  `active` status + approved KYC + verified equipment + no active order +
  known coordinates. An unvetted rider can never receive pings.

## 2. Ping dispatch engine

### The ping chain (no background worker)

1. `fleet.dispatch(db, delivery)` ranks dispatchable riders by haversine
   distance from the pickup point (shop location) and creates one offer per
   rider, **nearest first**: position 1 is `pending` with a 30s expiry,
   everyone else is parked `queued`.
2. The rider sees live offers via `GET /delivery/offers/me`.
3. `POST /delivery/offers/{offer_id}/accept` validates the window is still
   open, cancels sibling offers, attaches the rider, and marks the delivery
   `assigned` (same effect as an admin manual assign).
4. `decline` or expiry (`fleet.expire_stale_offers`, invoked lazily before
   reads) promotes the next queued rider with a fresh countdown via
   `fleet.promote_next_in_queue()` — the design's sequential 30-second
   fallback, achieved without a scheduler.

### Auto-dispatch

`fleet.auto_dispatch_group(db, order_group)` runs inside `_mark_order_paid`
(the single choke point every successful payment — M-Pesa or Paystack —
passes through). For each order carrying a delivery charge (per-order fee, or
its share of the group fee) **with shop coordinates**, it creates a `pending`
`Delivery` (tracking number included) and opens the ping window. If no rider
is in range it is a harmless no-op: the order still appears in the admin
**orders needing delivery** queue for manual handling or a manual dispatch
button press.

### Manual fallbacks (admin pages)

- **Dispatch button** → `POST /delivery/{order_id}/dispatch` re-pings pending
  deliveries (e.g. after auto-dispatch found nobody).
- **Assign** → `POST /delivery/{order_id}/assign` attaches a chosen rider and
  calls `fleet.cancel_open_offers()` so a ping can never be accepted over a
  manual assignment. Reassignment frees the previous rider's
  `current_order_id`.

## 3. Wallet ledger & B2C payouts

- On delivery completion the rider's share of the fee is credited once
  (idempotent) by `fleet.credit_delivery_earnings()`.
- **Admin-triggered payout** (`POST /delivery/admin/ledger/{agent_id}/payout`,
  shown on the admin **Rider Ledger** page) posts a **pending** debit and calls
  Daraja B2C. `ResponseCode 0` from initiation only means *queued* — the entry
  stays pending and `reference` records the `OriginatorConversationID`.
- The **only** finalizers are the Daraja callbacks:
  - `POST /payments/b2c/callback` → `ResultCode 0` marks the entry
    `succeeded` with the real M-Pesa `TransactionID`; any other `ResultCode`
    marks it `failed` and posts an **offsetting reversal entry** restoring the
    wallet (via `fleet.mark_payout_result()`).
  - `POST /payments/b2c/timeout` → same failure path (queue timeout).
- Both webhooks authenticate via `verify_mpesa_callback_token` (same token
  scheme as the STK callback). Fallback Result/Timeout URLs are signed with
  `?token=` when `MPESA_CALLBACK_SECRET` is set; if you register `ResultURL` in
  the Daraja portal manually, it will 401 when a secret is configured.
- **Reversal** (`POST /delivery/admin/ledger/{entry_id}/reverse`) only applies
  to a `succeeded` `b2c_payout`: it fires a Daraja reversal (best-effort) and
  credits the wallet with a `reversal` ledger entry regardless so balances stay
  consistent.

## 4. Metered pricing & surge

`GET /delivery/pricing-rules` + `PUT /delivery/pricing-rules/{vehicle_type}`
(admin **Pricing Rules** page):

```
base_fare + per_km×km + per_min×min
  × max(1.00, rain × peak-hours × supply/demand)   # surge
  → capped at max_surge_cap
```

- Peak hours = 17:00–20:00, Mon–Sat (East Africa time).
- `POST /delivery/quote` computes a quote. When `raining` is omitted and
  `origin_lat/lng` are provided, it live-checks OpenWeather
  (`fleet.fetch_raining`) and applies the rain multiplier only when
  precipitation is present. Weather lookups fail **soft** (to no-rain) so a
  quote never depends on OpenWeather availability.

---

## API surface

### Backend (`/delivery`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/login` | — | Rider login. |
| POST / GET | `/agents` | admin | Create / list delivery agents. |
| GET | `/agents/me`, `/me` | rider | Profile. |
| PATCH | `/agents/me/status`, `/agents/me/location` | rider | Availability / live location. |
| GET | `/agents/me/earnings`, `/agents/me/ledger` | rider | Rider earnings & wallet. |
| GET | `/agents/locations` | admin | Map markers. |
| GET / PUT | `/kyc/me` | rider | Submit / read own KYC. |
| GET | `/admin/kyc` | admin | KYC review queue (filterable by status). |
| POST | `/admin/kyc/{agent_id}/approve` | admin | Approve + mark equipment verified. |
| POST | `/admin/kyc/{agent_id}/reject` | admin | Reject + deactivate rider. |
| POST | `/{order_id}/dispatch` | admin | Open/refresh the ping window. |
| GET | `/offers/me` | rider | Live ping offers (expires stale first). |
| POST | `/offers/{offer_id}/accept`, `/decline` | rider | Respond to a ping. |
| POST | `/offers/expire-stale` | admin | Manually nudge expiry sweep. |
| GET | `/admin/ledger` | admin | Rider ledger + wallet balance. |
| POST | `/admin/ledger/{agent_id}/payout` | admin | Trigger B2C payout (pending until callback). |
| POST | `/admin/ledger/{entry_id}/reverse` | admin | Reverse a settled payout. |
| GET | `/pricing-rules` | admin | List metered rules. |
| PUT | `/pricing-rules/{vehicle_type}` | admin | Create/update a rule. |
| POST | `/quote` | admin | Metered quote with surge. |
| GET | `/rates`, `/simulate` | admin | Legacy flat-fee tariffs / simulator. |
| GET | `/{order_id}/track`, `/{delivery_id}` | — | Tracking / delivery detail. |

### Backend (`/payments`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/b2c/callback` | callback token | Settles/fails a pending B2C payout from Daraja's Result. |
| POST | `/b2c/timeout` | callback token | Fails a pending payout on queue timeout (wallet restored). |

### Frontend

| Page | BFF → backend | What it does |
|---|---|---|
| `/admin/kyc` | `/api/admin/fleet/kyc/*` | Approve / reject rider KYC, pending count. |
| `/admin/ledger` | `/api/admin/fleet/ledger/*` | Browse any rider's ledger, send B2C payout, reverse. |
| `/admin/deliveries` | `/api/admin/delivery/{orderId}/dispatch` + `/assign` | Manual dispatch button + rider assignment. |
| `/admin/pricing-rules` | `/api/admin/fleet/pricing/*` | Edit per-vehicle metered rates and surge multipliers. |
| Rider PWA (`/agent/*`) | `/api/agent/*` | Ping panel (5s poll, countdown, accept/decline), KYC submission, earnings/ledger. |

---

## Design notes

- **No background workers.** Stale-ping expiry runs lazily inside reads;
  payouts settle only via callbacks. Deployments that prefer cron can call
  `POST /delivery/offers/expire-stale`.
- **Radius scans use haversine in Python** (the schema keeps plain lat/lng, no
  PostGIS). `fleet.find_candidates()` is the single function to re-implement
  with `ST_DWithin()` if PostGIS is enabled — callers stay unchanged.
- **Decimal discipline.** Money is `Decimal` end to end; every mutation is a
  ledger row with `balance_after`, and payouts are provisional (`pending`)
  until Daraja confirms.
- **Idempotency.** Earnings credit once per delivery; `mark_payout_*` no-ops on
  non-pending entries; reversal is guarded to `succeeded b2c_payout` rows.
- **Route ordering.** `GET /{delivery_id}` is registered last in
  `routers/delivery.py` so static single-segment routes (e.g. `/rates`,
  `/pricing-rules`, `/quote`) are never shadowed; keep new static routes above
  it.