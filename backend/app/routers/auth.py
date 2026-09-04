import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    generate_short_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.dependencies.auth import bearer_scheme, get_current_user
from app.dependencies.database import get_db
from app.services import email as email_service
from app.services import paystack
from app.services.subscriptions import activate_subscription
from app.models.shop import Shop, ShopStatus
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import (
    EmailVerification,
    EmailVerificationPurpose,
    PasswordReset,
    RefreshToken,
    User,
    UserRole,
    UserStatus,
)
from app.schemas.user import LoginRequest, RegisterResponse, ResetPasswordRequest, TokenResponse, UserCreate, UserRead
from app.schemas.subscription import (
    ResumePaymentRequest,
    ResumePaymentResponse,
    SubscriptionStatusResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _generate_unique_shop_slug(db: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "shop"
    slug = base
    suffix = 1
    while db.query(Shop).filter(Shop.slug == slug).first():
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    description="""
Create a new buyer or seller account.

**Buyers:**
1. Validates that the email is not already taken.
2. Creates the user with status `pending` (cannot log in yet).
3. Generates a 24-hour email verification token and emails it.
   The account remains `pending` until `/auth/verify-email` is called.

**Sellers** (requires `shop_name` and `plan_code`):
1. Validates the email and looks up the chosen `SubscriptionPlan`.
2. Creates the user, a `Shop` (status `pending`), and a `Subscription`
   (status `pending_payment`) to the chosen plan.
3. Initializes a Paystack transaction for the plan's monthly price and
   returns its `authorization_url` for the client to redirect to.

No verification email is sent for sellers — payment confirmation (via the
Paystack webhook, or `/auth/subscription-status`) is what activates the
user, the shop, and the subscription.
""",
)
@limiter.limit("5/minute")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        county=payload.county,
        role=payload.role,
    )
    db.add(user)
    db.flush()

    if payload.role == UserRole.seller:
        plan = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.code == payload.plan_code,
            SubscriptionPlan.is_active == True,
        ).first()
        if not plan:
            db.rollback()
            raise HTTPException(status_code=404, detail="Unknown or inactive plan")

        shop = Shop(
            seller_id=user.id,
            name=payload.shop_name,
            slug=_generate_unique_shop_slug(db, payload.shop_name),
            status=ShopStatus.pending,
        )
        db.add(shop)
        try:
            db.flush()
        except IntegrityError:
            # two concurrent registrations computed the same slug before either committed
            db.rollback()
            raise HTTPException(status_code=409, detail="That shop name is taken, please try a different one")

        subscription = Subscription(
            shop_id=shop.id,
            plan_id=plan.id,
            status=SubscriptionStatus.pending_payment,
        )
        db.add(subscription)
        db.flush()

        reference = f"eks_sub_{uuid.uuid4().hex[:20]}"
        try:
            result = paystack.initialize_transaction(
                email=user.email,
                amount=plan.price_monthly,
                reference=reference,
                callback_url=f"{settings.FRONTEND_URL}/register/payment-status?ref={reference}",
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=502, detail=f"Paystack error: {str(e)}")

        subscription.provider_ref = reference
        db.commit()
        db.refresh(user)

        return RegisterResponse(
            user=user,
            authorization_url=result["authorization_url"],
            reference=reference,
        )

    verification = EmailVerification(
        user_id=user.id,
        token=generate_short_token(32),
        purpose=EmailVerificationPurpose.email_verify,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(verification)
    db.commit()
    db.refresh(user)

    try:
        email_service.send_verification_email(user.email, verification.token)
    except Exception as e:
        logger.warning("Failed to send verification email to %s: %s", user.email, e)

    return RegisterResponse(user=user)


@router.post(
    "/verify-email",
    summary="Verify email address",
    description="""
Activate an account using the token sent during registration.

**Flow:**
1. Looks up the token in `email_verifications`: must be unused and not expired.
2. Sets the user's status from `pending` → `active`.
3. Marks the token as used (one-time use).

Tokens expire after **24 hours**. After expiry, the user must re-register
or a resend endpoint must be added.
""",
)
def verify_email(token: str, db: Session = Depends(get_db)):
    verification = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.token == token,
            EmailVerification.purpose == EmailVerificationPurpose.email_verify,
            EmailVerification.used_at.is_(None),
        )
        .first()
    )

    if not verification:
        raise HTTPException(status_code=400, detail="Invalid or already used token")

    if verification.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token has expired")

    user = db.query(User).filter(User.id == verification.user_id).first()
    user.status = UserStatus.active
    verification.used_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Email verified. You can now log in."}


@router.get(
    "/subscription-status/{reference}",
    response_model=SubscriptionStatusResponse,
    summary="Check a pending seller subscription's payment status",
    description="""
Used by the registration payment-return page (and the renewal payment-return
page — the seller may not be looking at an authenticated page at this point
in either flow), so this endpoint requires no auth.

If the subscription isn't yet `active`, re-checks Paystack directly in case
the webhook hasn't landed yet (same reconciliation pattern used for order
payments in `/payments/paystack/verify/{reference}`). This covers both a
fresh registration (`pending_payment` -> `active`) and a renewal payment
(`past_due`/`cancelled` -> `active`).
""",
)
def subscription_status(reference: str, db: Session = Depends(get_db)):
    subscription = db.query(Subscription).filter(Subscription.provider_ref == reference).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found for this reference")

    if subscription.status != SubscriptionStatus.active:
        try:
            result = paystack.verify_transaction(reference)
        except Exception:
            result = {}
        if result.get("status") == "success":
            activate_subscription(db, subscription)
            db.commit()

    return SubscriptionStatusResponse(status=subscription.status, shop_slug=subscription.shop.slug)


@router.post(
    "/resume-payment",
    response_model=ResumePaymentResponse,
    summary="Retry payment for an abandoned seller registration",
    description="""
Generates a fresh Paystack transaction for a subscription that is still
`pending_payment` — for a seller who closed the checkout tab before paying.
""",
)
def resume_payment(payload: ResumePaymentRequest, db: Session = Depends(get_db)):
    subscription = db.query(Subscription).filter(
        Subscription.provider_ref == payload.reference,
        Subscription.status == SubscriptionStatus.pending_payment,
    ).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="No pending payment found for this reference")

    new_reference = f"eks_sub_{uuid.uuid4().hex[:20]}"
    try:
        result = paystack.initialize_transaction(
            email=subscription.shop.seller.email,
            amount=subscription.plan.price_monthly,
            reference=new_reference,
            callback_url=f"{settings.FRONTEND_URL}/register/payment-status?ref={new_reference}",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Paystack error: {str(e)}")

    subscription.provider_ref = new_reference
    db.commit()

    return ResumePaymentResponse(authorization_url=result["authorization_url"], reference=new_reference)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive tokens",
    description="""
Authenticate with email and password.

**Flow:**
1. Looks up the user by email (case-insensitive; email is normalised on input).
2. Verifies the password against the bcrypt hash.
3. Rejects `pending` (unverified) and `suspended` accounts with distinct 403 messages.
4. Issues a short-lived **access token** (JWT, default 15 min).
5. Issues a long-lived **refresh token** (opaque random string, default 7 days).
   - The raw token is returned to the client.
   - Only a SHA-256 hash of the token is stored in the database.
6. Updates `last_login_at` on the user record.

**Token usage:**
- Send the access token as `Authorization: Bearer <access_token>` on every protected request.
- Use the refresh token with `/auth/refresh` to get a new pair before the access token expires.
""",
)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.status == UserStatus.pending:
        if user.role == UserRole.seller:
            raise HTTPException(
                status_code=403,
                detail="Your registration payment hasn't been confirmed yet. Complete payment to activate your shop.",
            )
        raise HTTPException(status_code=403, detail="Please verify your email first")

    if user.status == UserStatus.suspended:
        raise HTTPException(status_code=403, detail="Account suspended. Contact support.")

    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        expires_delta=timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS),
    )

    raw_refresh = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh an access token",
    description="""
Exchange a valid refresh token for a new access + refresh token pair.

**Flow:**
1. Hashes the incoming raw token with SHA-256 and looks it up in `refresh_tokens`.
2. Validates it is not revoked and not expired.
3. Revokes the old refresh token immediately (**token rotation**: each refresh
   token can only be used once, preventing replay attacks).
4. Issues a fresh access token and a new refresh token.

If the same refresh token is used twice, the second call will fail with 401.
""",
)
def refresh(raw_token: str, db: Session = Depends(get_db)):
    stored = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == hash_refresh_token(raw_token),
            RefreshToken.revoked_at.is_(None),
        )
        .first()
    )

    if not stored or stored.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = db.query(User).filter(User.id == stored.user_id).first()

    stored.revoked_at = datetime.now(timezone.utc)

    new_access = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        expires_delta=timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS),
    )
    new_raw_refresh = generate_refresh_token()
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(new_raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    db.commit()

    return TokenResponse(access_token=new_access, refresh_token=new_raw_refresh)


@router.post(
    "/logout",
    summary="Log out and revoke refresh token",
    description="""
Revoke the current refresh token, invalidating the session.

**Flow:**
1. Requires a valid access token in the `Authorization` header (proves the caller
   owns the session being terminated).
2. Looks up the refresh token by its SHA-256 hash and marks it as revoked.
3. The access token itself is **not** invalidated server-side (it is stateless and
   will expire naturally after its TTL). The client must discard it.

For a full immediate logout, the client should discard both tokens after calling this.
""",
)
def logout(
    raw_token: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stored = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == hash_refresh_token(raw_token),
            RefreshToken.revoked_at.is_(None),
        )
        .first()
    )
    if stored:
        stored.revoked_at = datetime.now(timezone.utc)
        db.commit()

    return {"message": "Logged out"}


@router.post(
    "/forgot-password",
    summary="Request a password reset link",
    description="""
Send a password reset email to the given address.

**Flow:**
1. Looks up the user silently; **always returns the same response** regardless of
   whether the email exists. This prevents user enumeration attacks.
2. If the user exists, generates a 1-hour reset token and stores it in `password_resets`.
3. (Production) Sends an email with a link containing the token.

In dev, the token is printed to the terminal.
""",
)
@limiter.limit("5/minute")
def forgot_password(request: Request, email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()

    if user:
        reset = PasswordReset(
            user_id=user.id,
            token=generate_short_token(32),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(reset)
        db.commit()

        try:
            email_service.send_password_reset_email(email, reset.token)
        except Exception as e:
            logger.warning("Failed to send password reset email to %s: %s", email, e)

    return {"message": "If that email is registered you will receive a reset link"}


@router.post(
    "/reset-password",
    summary="Set a new password using a reset token",
    description="""
Complete a password reset initiated via `/auth/forgot-password`.

**Flow:**
1. Validates the reset token: must exist, be unused, and not expired (1-hour TTL).
2. Hashes the new password and updates the user record.
3. Marks the reset token as used (one-time use only).
4. **Revokes all active refresh tokens** for this user, forcing re-login on all
   devices, a standard security practice after a credential change.
""",
)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset = (
        db.query(PasswordReset)
        .filter(
            PasswordReset.token == payload.token,
            PasswordReset.used_at.is_(None),
        )
        .first()
    )

    if not reset or reset.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.id == reset.user_id).first()
    user.password_hash = hash_password(payload.new_password)
    reset.used_at = datetime.now(timezone.utc)

    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None),
    ).update({"revoked_at": datetime.now(timezone.utc)})

    db.commit()

    return {"message": "Password updated. Please log in again."}
