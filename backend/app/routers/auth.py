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
from app.services.geography import resolve_county_name
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


def _email_is_verified(db: Session, user: User) -> bool:
    """Whether this user has confirmed their email address.

    `status` can't answer this on its own for sellers: they stay `pending`
    after verifying, because payment is what activates them.

    Sellers who registered before verification was added to the seller flow
    have no `email_verifications` row at all and were never sent a link. They
    count as verified here, otherwise they'd be told to check an inbox for an
    email that does not exist.
    """
    verifications = (
        db.query(EmailVerification)
        .filter(
            EmailVerification.user_id == user.id,
            EmailVerification.purpose == EmailVerificationPurpose.email_verify,
        )
        .all()
    )
    if not verifications:
        return True
    return any(v.used_at is not None for v in verifications)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    description="""
Create a new buyer or seller account.

Names, phone number and county are validated and normalised first (see
`app.core.validators`): the phone is stored as `2547XXXXXXXX` whatever
shape it was typed in, and the county must match one of the 47 rows in the
`counties` table.

**Buyers:**
1. Validates that the email is not already taken.
2. Creates the user with status `pending` (cannot log in yet).
3. Generates a 24-hour email verification token and emails it.
   The account remains `pending` until `/auth/verify-email` is called.

**Sellers** (requires `shop_name` and `plan_code`):
1. Validates the email and looks up the chosen `SubscriptionPlan`.
2. Creates the user, a `Shop` (status `pending`), and a `Subscription`
   (status `pending_payment`) to the chosen plan.
3. Sends the same verification email buyers get.

Sellers verify their email *before* they can pay, and registration
deliberately opens no payment session, so an unverified address can never
reach checkout. After verifying they sign in and land on the locked
dashboard, where payment is started from `/subscriptions/me/renew`.
Payment confirmation (via the Paystack webhook, or
`/auth/subscription-status`) is what activates the user, the shop, and the
subscription.
""",
)
@limiter.limit("5/minute")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        county = resolve_county_name(db, payload.county)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        county=county,
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

        # No Paystack transaction yet: the seller opens one by verifying their
        # email, so a scraped or mistyped address can't reach checkout.
        subscription = Subscription(
            shop_id=shop.id,
            plan_id=plan.id,
            status=SubscriptionStatus.pending_payment,
        )
        db.add(subscription)
        db.flush()

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
        email_service.send_verification_email(
            user.email,
            verification.token,
            is_seller=user.role == UserRole.seller,
        )
    except Exception as e:
        logger.warning("Failed to send verification email to %s: %s", user.email, e)

    return RegisterResponse(user=user)


@router.post(
    "/verify-email",
    summary="Verify email address",
    description="""
Confirm an email address using the token sent during registration.

**Flow:**
1. Looks up the token in `email_verifications`: must be unused and not expired.
2. Marks the token as used (one-time use).
3. **Buyers:** sets the user's status from `pending` → `active`; they can log in.
4. **Sellers:** the account stays `pending`, because payment is what activates a
   seller. They can sign in from here all the same — `/auth/login` issues a
   token once the email is verified — and the dashboard renders locked until
   the subscription is paid for.

Tokens expire after **24 hours**; `/auth/resend-verification` issues a new one.
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
    verification.used_at = datetime.now(timezone.utc)

    # A seller stays `pending` -- payment, not verification, is what activates
    # them. They can still sign in from here: login issues a token once the
    # email is verified, and the dashboard renders locked until they pay.
    if user.role != UserRole.seller:
        user.status = UserStatus.active

    db.commit()

    if user.role == UserRole.seller:
        return {
            "message": "Email verified. Sign in to activate your shop.",
            "next": "login",
            "seller": True,
        }

    return {"message": "Email verified. You can now log in.", "next": "login"}


@router.get(
    "/subscription-status/{reference}",
    response_model=SubscriptionStatusResponse,
    summary="Check a pending seller subscription's payment status",
    description="""
Used by the registration payment-return page (and the renewal payment-return
page — the seller may not be looking at an authenticated page at this point
in either flow), so this endpoint requires no auth.

If this reference's payment hasn't yet been applied, re-checks Paystack
directly in case the webhook hasn't landed yet (same reconciliation pattern
used for order payments in `/payments/paystack/verify/{reference}`). This
covers a fresh registration (`pending_payment` -> `active`), a renewal
payment (`past_due`/`cancelled` -> `active`), and an early renewal (already
`active`, extending the period) — the check is keyed on whether *this*
reference was applied, not on `status == active`, since an early renewal
starts out already active and would otherwise be reported as confirmed
before Paystack has actually settled it.
""",
)
def subscription_status(reference: str, db: Session = Depends(get_db)):
    subscription = db.query(Subscription).filter(Subscription.provider_ref == reference).first()
    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found for this reference")

    payment_confirmed = subscription.last_activated_ref == reference
    if not payment_confirmed:
        try:
            result = paystack.verify_transaction(reference)
        except Exception:
            result = {}
        if result.get("status") == "success":
            activate_subscription(db, subscription)
            db.commit()
            payment_confirmed = subscription.last_activated_ref == reference

    return SubscriptionStatusResponse(
        status=subscription.status,
        shop_slug=subscription.shop.slug,
        payment_confirmed=payment_confirmed,
    )


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
        # A seller who has verified but not yet paid is let in on purpose: they
        # get a session and land on the locked dashboard, where they can choose
        # to pay, switch plan, or just look around. The paywall is enforced per
        # endpoint from there (see dependencies.auth), not by refusing login.
        # Everyone else pending -- buyers, and sellers who never verified --
        # still stops here.
        if not (user.role == UserRole.seller and _email_is_verified(db, user)):
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
    "/resend-verification",
    summary="Send a fresh email verification link",
    description="""
Re-send the verification email for an account still waiting on it.

Verification tokens expire after 24 hours, and this is the only way back for
someone who let one lapse or lost the email — which matters most for sellers,
since they can't reach payment until they verify.

Like `/auth/forgot-password`, this **always returns the same response** so it
can't be used to discover which addresses are registered. Nothing is sent for
an account that is already active, or for a seller who has verified and is
only waiting on payment (they get sent back to checkout from the login page
instead). Previously-issued tokens are left valid until they expire.
""",
)
@limiter.limit("3/minute")
def resend_verification(request: Request, email: str, db: Session = Depends(get_db)):
    generic_response = {"message": "If that account still needs verifying, we've sent a new link"}

    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or user.status != UserStatus.pending or _email_is_verified(db, user):
        return generic_response

    verification = EmailVerification(
        user_id=user.id,
        token=generate_short_token(32),
        purpose=EmailVerificationPurpose.email_verify,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(verification)
    db.commit()

    try:
        email_service.send_verification_email(
            user.email,
            verification.token,
            is_seller=user.role == UserRole.seller,
        )
    except Exception as e:
        logger.warning("Failed to resend verification email to %s: %s", user.email, e)

    return generic_response


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
