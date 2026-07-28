import base64
import httpx
from datetime import datetime
from app.core.config import settings

def get_access_token() -> str:
    credentials = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    response = httpx.get(
        f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
        headers={"Authorization": f"Basic {encoded}"},
    )
    response.raise_for_status()
    return response.json()["access_token"]

def initiate_stk_push(access_token: str, phone: str, amount: int, order_ref: str) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    # password = base64(shortcode + passkey + timestamp)
    raw_password = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(raw_password.encode()).decode()

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": f"{settings.MPESA_CALLBACK_URL}/payments/mpesa/callback",
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