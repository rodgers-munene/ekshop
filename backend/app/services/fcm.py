"""FCM (Firebase Cloud Messaging) service for push notifications."""

import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

# FCM API endpoint
FCM_API_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

# Scope for FCM
FCM_SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]


class FCMError(Exception):
    """FCM service error."""
    pass


class FCMClient:
    """Firebase Cloud Messaging client using service account authentication."""

    def __init__(self):
        self._credentials: Optional[service_account.Credentials] = None
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    def _load_credentials(self) -> service_account.Credentials:
        """Load service account credentials from settings."""
        if not all([
            settings.FCM_PROJECT_ID,
            settings.FCM_PRIVATE_KEY_ID,
            settings.FCM_PRIVATE_KEY,
            settings.FCM_CLIENT_EMAIL,
            settings.FCM_CLIENT_ID,
        ]):
            raise FCMError("FCM credentials not configured. Set FCM_* environment variables.")

        # Reconstruct the private key (replace escaped newlines)
        private_key = settings.FCM_PRIVATE_KEY.replace("\\n", "\n")

        service_account_info = {
            "type": "service_account",
            "project_id": settings.FCM_PROJECT_ID,
            "private_key_id": settings.FCM_PRIVATE_KEY_ID,
            "private_key": private_key,
            "client_email": settings.FCM_CLIENT_EMAIL,
            "client_id": settings.FCM_CLIENT_ID,
            "auth_uri": settings.FCM_AUTH_URI,
            "token_uri": settings.FCM_TOKEN_URI,
            "auth_provider_x509_cert_url": settings.FCM_AUTH_PROVIDER_CERT_URL,
            "client_x509_cert_url": settings.FCM_CLIENT_CERT_URL,
        }

        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=FCM_SCOPES,
        )
        return credentials

    def _get_credentials(self) -> service_account.Credentials:
        """Get or create credentials."""
        if self._credentials is None:
            self._credentials = self._load_credentials()
        return self._credentials

    async def _get_access_token(self) -> str:
        """Get valid access token, refreshing if needed."""
        if self._access_token and self._token_expires and datetime.now() < self._token_expires:
            return self._access_token

        credentials = self._get_credentials()
        request = Request()
        credentials.refresh(request)
        self._access_token = credentials.token
        # Token expires in ~1 hour, refresh 5 min early
        self._token_expires = datetime.now() + timedelta(minutes=55)
        return self._access_token

    async def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send request to FCM API."""
        if not settings.FCM_ENABLED:
            raise FCMError("FCM is not enabled. Set FCM_ENABLED=true.")

        access_token = await self._get_access_token()
        url = FCM_API_URL.format(project_id=settings.FCM_PROJECT_ID)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", error_detail)
            except Exception:
                pass
            raise FCMError(f"FCM API error {response.status_code}: {error_detail}")

        return response.json()

    async def send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a notification to a single FCM token."""
        message = {
            "token": token,
            "notification": {
                "title": title,
                "body": body,
            },
            "android": {
                "priority": "high",
                "notification": {
                    "click_action": "FLUTTER_NOTIFICATION_CLICK",
                    "channel_id": "default",
                },
            },
            "apns": {
                "payload": {
                    "aps": {
                        "alert": {
                            "title": title,
                            "body": body,
                        },
                        "sound": "default",
                        "badge": 1,
                    },
                },
            },
            "webpush": {
                "headers": {
                    "Urgency": "high",
                },
            },
        }

        if image_url:
            message["android"]["notification"]["image"] = image_url
            message["apns"]["payload"]["aps"]["mutable-content"] = 1
            message["webpush"]["headers"]["Image"] = image_url

        if data:
            message["data"] = {k: str(v) for k, v in data.items()}

        return await self._send_request({"message": message})

    async def send_to_multiple_tokens(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Send notification to multiple tokens (batch send via multicast)."""
        if not tokens:
            return []

        # FCM multicast supports up to 500 tokens per request
        results = []
        for i in range(0, len(tokens), 500):
            batch = tokens[i:i + 500]
            payload = {
                "message": {
                    "notification": {"title": title, "body": body},
                    "android": {"priority": "high"},
                    "apns": {"payload": {"aps": {"alert": {"title": title, "body": body}, "sound": "default"}}},
                    "tokens": batch,
                }
            }
            if data:
                payload["message"]["data"] = {k: str(v) for k, v in data.items()}

            results.append(await self._send_request(payload))
        return results

    async def send_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, str]] = None,
        image_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send notification to a topic."""
        message = {
            "topic": topic,
            "notification": {"title": title, "body": body},
            "android": {"priority": "high"},
            "apns": {"payload": {"aps": {"alert": {"title": title, "body": body}, "sound": "default"}}},
        }
        if data:
            message["data"] = {k: str(v) for k, v in data.items()}
        if image_url:
            message["android"]["notification"] = {"image": image_url}
            message["apns"]["payload"]["aps"]["mutable-content"] = 1

        return await self._send_request({"message": message})


# Singleton instance
fcm_client = FCMClient()


async def send_push_notification(
    user_id: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    db_session=None,
) -> bool:
    """
    High-level function to send push notification to a user.

    Args:
        user_id: User ID (UUID string)
        title: Notification title
        body: Notification body
        data: Optional data payload
        db_session: Optional DB session to look up user's FCM token

    Returns:
        True if notification was sent, False otherwise.
    """
    if not settings.FCM_ENABLED:
        logger.info("FCM not enabled, skipping push notification")
        return False

    # If db_session provided, look up user's FCM token
    token = None
    if db_session:
        user = db_session.query(User).filter(User.id == user_id).first()
        if user and user.fcm_token:
            token = user.fcm_token

    if not token:
        logger.warning(f"No FCM token for user {user_id}, skipping push notification")
        return False

    try:
        await fcm_client.send_to_token(token, title, body, data)
        return True
    except FCMError as e:
        logger.error(f"Failed to send push notification to user {user_id}: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error sending push to user {user_id}")
        return False


async def send_push_to_multiple(
    user_ids: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None,
    db_session=None,
) -> int:
    """Send push notification to multiple users. Returns count of successful sends."""
    if not settings.FCM_ENABLED or not user_ids:
        return 0

    tokens = []
    if db_session:
        users = db_session.query(User).filter(User.id.in_(user_ids)).all()
        for user in users:
            if user.fcm_token:
                tokens.append(user.fcm_token)

    if not tokens:
        return 0

    try:
        results = await fcm_client.send_to_multiple_tokens(tokens, title, body, data)
        # Count successful sends from results
        success_count = sum(1 for r in results if r.get("successCount", 0) > 0)
        return success_count
    except Exception as e:
        logger.exception(f"Failed to send push to multiple users: {e}")
        return 0