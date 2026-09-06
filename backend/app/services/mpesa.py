import base64
import re
import httpx
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from app.core.config import settings

# Kenya has a fixed UTC+3 offset with no DST, so this is always correct —
# unlike datetime.now(), which is only right if the host's local timezone
# happens to be set to Africa/Nairobi (it isn't in the deployed container:
# the Docker base image has no tzdata/TZ set and defaults to UTC, which
# would otherwise send Safaricom a timestamp 3 hours off on every request).
def _eat_timestamp() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y%m%d%H%M%S")


def _build_password(timestamp: str) -> str:
    raw_password = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    return base64.b64encode(raw_password.encode()).decode()


def get_access_token() -> str:
    credentials = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    response = httpx.get(
        f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
        headers={"Authorization": f"Basic {encoded}"},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def normalize_phone(raw: str) -> str:
    """Normalizes a Safaricom mobile number to the 2547XXXXXXXX/2541XXXXXXXX
    form the Daraja API requires, accepting the common formats buyers type
    (07..., 7..., +2547..., 2547...)."""
    digits = re.sub(r"\D", "", raw)

    if digits.startswith("254") and len(digits) == 12:
        normalized = digits
    elif digits.startswith("0") and len(digits) == 10:
        normalized = "254" + digits[1:]
    elif len(digits) == 9:
        normalized = "254" + digits
    else:
        raise ValueError(f"Not a recognizable Safaricom phone number: {raw}")

    if not re.match(r"^254[17]\d{8}$", normalized):
        raise ValueError(f"Not a recognizable Safaricom phone number: {raw}")

    return normalized


def initiate_stk_push(access_token: str, phone: str, amount: int, order_ref: str) -> dict:
    timestamp = _eat_timestamp()
    password = _build_password(timestamp)
    callback_url = f"{settings.MPESA_CALLBACK_URL}/payments/mpesa/callback?token={quote(settings.MPESA_CALLBACK_SECRET or '')}"

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerBuyGoodsOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": settings.MPESA_TILL_NUMBER or settings.MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": order_ref,
        "TransactionDesc": "Ekshop order payment",
    }

    response = httpx.post(
        f"{settings.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()

    return response.json()


def query_stk_push_status(access_token: str, checkout_request_id: str) -> dict:
    """Actively asks Safaricom for the result of a previously-initiated STK
    push, for when our own callback hasn't arrived (or never will). Returns
    {"pending": True} while the buyer hasn't yet completed the prompt on
    their phone — Safaricom reports that as an HTTP 500 error response
    (errorCode 500.001.1001), not a real error."""
    timestamp = _eat_timestamp()
    password = _build_password(timestamp)

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": checkout_request_id,
    }

    response = httpx.post(
        f"{settings.MPESA_BASE_URL}/mpesa/stkpushquery/v1/query",
        json=payload,
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if response.status_code == 500:
        body = response.json()
        if body.get("errorCode") == "500.001.1001":
            return {"pending": True}

    response.raise_for_status()
    return response.json()
