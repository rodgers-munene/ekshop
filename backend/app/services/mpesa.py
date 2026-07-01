import base64
import httpx
from datetime import datetime
from app.core.config import MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET, MPESA_BASE_URL, MPESA_SHORTCODE, MPESA_PASSKEY, MPESA_CALLBACK_URL

def get_access_token() -> str:
    credentials = f"{MPESA_CONSUMER_KEY}:{MPESA_CONSUMER_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    
    response = httpx.get(
        f"{MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
        headers={"Authorization": f"Basic {encoded}"},
    )
    response.raise_for_status()
    return response.json()["access_token"]

def initiate_stk_push(access_token: str, phone: str, amount: int, order_ref: str) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # password = base64(shortcode + passkey + timestamp)
    raw_password=f"{MPESA_SHORTCODE}{MPESA_PASSKEY}{timestamp}"
    password = base64.b64encode(raw_password.encode()).decode()
    
    payload = {
        "BusinessShortCode": MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": f"{MPESA_CALLBACK_URL}/payments/mpesa/callback",
        "AccountReference": order_ref,
        "TransactionDesc": "Ekshop order payment",
    }
    
    
    response = httpx.post(
        f"{MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    
    return response.json()