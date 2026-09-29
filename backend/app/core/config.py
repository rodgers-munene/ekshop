from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    # Short-lived access tokens. The public sessions (buyer/seller/admin web
    # and the rider PWA) hold the JWT in a cookie with no refresh endpoint, so
    # this value is the real session lifetime. 15 minutes matches what
    # docs/auth_pipeline.md documents.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Comma-separated list of allowed frontend origins
    CORS_ORIGINS: str = "http://localhost:3000"
    # Primary frontend origin, used to build payment provider redirect URLs
    FRONTEND_URL: str = "http://localhost:3000"

    # Structured logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = False

    # M-Pesa Daraja API: the live checkout payment provider. Paystack is kept
    # only for seller subscription billing (see PAYSTACK_* below).
    MPESA_CONSUMER_KEY: str | None = None
    MPESA_CONSUMER_SECRET: str | None = None
    MPESA_SHORTCODE: str = "174379"
    MPESA_PASSKEY: str | None = None
    # Set only when the shortcode above is a Store/Organization number with a
    # separate Till (Buy Goods) number linked to it — the STK push password
    # is built from MPESA_SHORTCODE (what the passkey is bound to), but the
    # till receiving the money must be passed separately as PartyB. Leave
    # unset for a plain paybill/till where they're the same number.
    MPESA_TILL_NUMBER: str | None = None
    MPESA_ENVIRONMENT: str = "sandbox"
    # Bare origin (e.g. https://x.sslip.io) — app/services/mpesa.py appends
    # the /payments/mpesa/callback path itself. Must be HTTPS in production.
    MPESA_CALLBACK_URL: str | None = None
    # Shared secret appended as a query token on the callback URL, since
    # Safaricom's callback carries no signature (unlike Paystack's HMAC
    # webhook) and we can't dictate headers on its request to us — same
    # spirit as CRON_SECRET below, just carried in the URL instead.
    MPESA_CALLBACK_SECRET: str | None = None

    # Outbound webhook for successful payment events (Make/Zapier/automations).
    # Example: https://hook.us.make.com/...
    PAYMENT_SUCCESS_WEBHOOK_URL: str | None = None

    # Paystack: seller subscription billing only (checkout uses M-Pesa above).
    PAYSTACK_SECRET_KEY: str | None = None
    PAYSTACK_PUBLIC_KEY: str | None = None

    # Shared secret the GitHub Actions cron workflow presents to trigger the
    # daily subscription billing cycle (POST /internal/cron/billing-cycle)
    CRON_SECRET: str | None = None

    RESEND_API_KEY: str | None = None
    EMAIL_FROM: str = "Ekshop <notifications@mail.ekshop.store>"
    ADMIN_REPORT_EMAIL: str | None = None

    ALERT_MIN_GROSS_MARGIN_PCT: float = 90.0
    ALERT_MAX_MPESA_LATENCY_SECONDS: float = 2.0
    ALERT_MAX_HOSTING_COST_PER_ORDER: float = 20.0
    ALERT_MAX_ORDER_CANCELLATION_RATE: float = 10.0
    ALERT_MIN_ON_TIME_DELIVERY_RATE: float = 80.0
    ALERT_MAX_CART_ABANDONMENT_RATE: float = 70.0

    ORS_API_KEY: str | None = None
    ORS_BASE_URL: str = "https://api.openrouteservice.org"

    # ── Rider fleet ─────────────────────────────────────────────────────────
    # Radius (km) around the pickup point used by the automated ping engine to
    # find eligible riders for a delivery. Kept in sync with the app's own
    # 3–5 km design guidance; tune per market.
    PING_RADIUS_KM: float = 5.0
    # How long an individual rider has to accept a ping before the offer
    # expires and the ping engine promotes the next rider in the queue.
    PING_EXPIRY_SECONDS: int = 30
    # M-Pesa B2C (Business-to-Customer) payout credentials + result callback.
    # PartyA for B2C must be a utility/storage M-Pesa shortcode (B2C is not
    # supported on buy-goods tills). SecurityCredential is derived by
    # base64-encrypting initiator password with the API certificate.
    MPESA_B2C_INITIATOR_NAME: str | None = None
    MPESA_B2C_INITIATOR_PASSWORD: str | None = None
    MPESA_B2C_SECURITY_CREDENTIAL: str | None = None
    MPESA_B2C_SHORTCODE: str | None = None
    MPESA_RESULT_URL: str | None = None
    MPESA_TIMEOUT_URL: str | None = None
    # Default rider payout split: share of the order's delivery fee credited to
    # the rider's ledger on delivery (0.80 = 80/20 rider/platform). Admin can
    # override per-order via the ledger API.
    RIDER_PAYOUT_SHARE: float = 0.80
    # OpenWeather key enabling rain/surge multiplier lookups for metered
    # pricing. Leave unset to run with surge disabled (multipliers = 1.00).
    OPENWEATHER_API_KEY: str | None = None

    # Product image storage (AWS S3): foundation only until AWS account access
    # is available; upload calls will fail until these are set.
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "eu-west-1"
    AWS_S3_BUCKET: str | None = None
    # Optional: CDN / custom domain fronting the bucket. Falls back to the
    # bucket's own public S3 URL when unset.
    AWS_S3_PUBLIC_URL: str | None = None

    @property
    def MPESA_BASE_URL(self) -> str:
        return (
            "https://api.safaricom.co.ke"
            if self.MPESA_ENVIRONMENT == "production"
            else "https://sandbox.safaricom.co.ke"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
