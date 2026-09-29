import base64
import re
import httpx
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from app.core.config import settings
from app.core.circuit_breaker import mpesa_circuit

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


DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def get_access_token() -> str:
    credentials = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    def _call() -> str:
        response = httpx.get(
            f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
            headers={"Authorization": f"Basic {encoded}"},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    return mpesa_circuit.call(_call)


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
        timeout=DEFAULT_TIMEOUT,
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

    def _call() -> dict:
        response = httpx.post(
            f"{settings.MPESA_BASE_URL}/mpesa/stkpushquery/v1/query",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=DEFAULT_TIMEOUT,
        )

        if response.status_code == 500:
            body = response.json()
            if body.get("errorCode") == "500.001.1001":
                return {"pending": True}

        response.raise_for_status()
        return response.json()

    return mpesa_circuit.call(_call, fallback=lambda: {"pending": True})


def initiate_b2c_payment(access_token: str, phone: str, amount: int, remarks: str, transaction_id: str) -> dict:
    """Fires a Daraja B2C payment to a rider's M-Pesa wallet (rider payout).

    Result/Timeout callbacks are delivered to the URLs configured in the
    Daraja sandbox/portal — MPESA_RESULT_URL/MPESA_TIMEOUT_URL are recorded
    here only for the webhook endpoint /payments/b2c/callback to reconcile
    against. Follows the standard three-legged flow:
      ResponseCode 0 + OriginatorConversationID -> queued, wait for callback.
    """
    if not settings.MPESA_B2C_INITIATOR_NAME or not settings.MPESA_B2C_SECURITY_CREDENTIAL:
        raise RuntimeError("MPESA_B2C initiator credentials are not configured")

    payload = {
        "InitiatorName": settings.MPESA_B2C_INITIATOR_NAME,
        "SecurityCredential": settings.MPESA_B2C_SECURITY_CREDENTIAL,
        "CommandID": "BusinessPayment",  # normal disbursement to a registered user
        "Amount": amount,
        "PartyA": settings.MPESA_B2C_SHORTCODE or settings.MPESA_SHORTCODE,
        "PartyB": phone,
        "Remarks": remarks,
        "QueueTimeOutURL": settings.MPESA_TIMEOUT_URL or f"{settings.MPESA_CALLBACK_URL}/payments/b2c/timeout",
        "ResultURL": settings.MPESA_RESULT_URL or f"{settings.MPESA_CALLBACK_URL}/payments/b2c/callback",
        "Occasion": "Rider payout",
    }

    def _call() -> dict:
        response = httpx.post(
            f"{settings.MPESA_BASE_URL}/mpesa/b2c/v1/paymentrequest",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    return mpesa_circuit.call(_call)


def initiate_b2c_reversal(access_token: str, transaction_id: str, amount: int) -> dict:
    """Reverses a previously-sent B2C payout. `transaction_id` is the
    Result Conversation / M-Pesa transaction ID from the successful B2C
    result callback (LedgerEntry.reference).
    """
    if not settings.MPESA_B2C_INITIATOR_NAME or not settings.MPESA_B2C_SECURITY_CREDENTIAL:
        raise RuntimeError("MPESA_B2C initiator credentials are not configured")

    payload = {
        "InitiatorName": settings.MPESA_B2C_INITIATOR_NAME,
        "SecurityCredential": settings.MPESA_B2C_SECURITY_CREDENTIAL,
        "CommandID": "Reversal",
        "TransactionID": transaction_id,
        "Amount": amount,
        "ReceiverParty": settings.MPESA_SHORTCODE,
        "ResultURL": settings.MPESA_RESULT_URL or f"{settings.MPESA_CALLBACK_URL}/payments/b2c/callback",
        "QueueTimeOutURL": settings.MPESA_TIMEOUT_URL or f"{settings.MPESA_CALLBACK_URL}/payments/b2c/timeout",
        "Remarks": "Rider payout reversal",
        "Occasion": "Reversal",
    }

    def _call() -> dict:
        response = httpx.post(
            f"{settings.MPESA_BASE_URL}/mpesa/reversal/v1/request",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    return mpesa_circuit.call(_call)
