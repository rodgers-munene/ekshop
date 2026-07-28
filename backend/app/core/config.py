from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Comma-separated list of allowed frontend origins
    CORS_ORIGINS: str = "http://localhost:3000"
    # Primary frontend origin, used to build payment provider redirect URLs
    FRONTEND_URL: str = "http://localhost:3000"

    # M-Pesa Daraja API: built but not yet linked into checkout (Daraja app
    # is not production-approved yet; Paystack is the live payment provider)
    MPESA_CONSUMER_KEY: str | None = None
    MPESA_CONSUMER_SECRET: str | None = None
    MPESA_SHORTCODE: str = "174379"
    MPESA_PASSKEY: str | None = None
    MPESA_ENVIRONMENT: str = "sandbox"
    MPESA_CALLBACK_URL: str | None = None

    PAYSTACK_SECRET_KEY: str | None = None
    PAYSTACK_PUBLIC_KEY: str | None = None

    RESEND_API_KEY: str | None = None
    EMAIL_FROM: str = "Ekshop <no-reply@ekshop.co.ke>"

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
