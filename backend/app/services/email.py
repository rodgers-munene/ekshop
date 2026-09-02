import html as html_lib
import logging
from typing import Iterable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def _send(to: str, subject: str, html: str) -> None:
    if not settings.RESEND_API_KEY:
        logger.info("[DEV] Email to %s: %s\n%s", to, subject, html)
        return

    response = httpx.post(
        RESEND_API_URL,
        json={"from": settings.EMAIL_FROM, "to": [to], "subject": subject, "html": html},
        headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
    )
    response.raise_for_status()


def send_verification_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    _send(
        to=to,
        subject="Verify your Ekshop account",
        html=f"""
            <p>Welcome to Ekshop!</p>
            <p><a href="{link}">Click here to verify your email</a> to activate your account.</p>
            <p>This link expires in 24 hours.</p>
        """,
    )


def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    _send(
        to=to,
        subject="Reset your Ekshop password",
        html=f"""
            <p>We received a request to reset your password.</p>
            <p><a href="{link}">Click here to set a new password</a>.</p>
            <p>This link expires in 1 hour. If you didn't request this, you can ignore this email.</p>
        """,
    )


def send_notification_email(to: str, title: str, body: str) -> None:
    _send(
        to=to,
        subject=title,
        html=f"""
            <p>{body}</p>
            <p><a href="{settings.FRONTEND_URL}/orders">View your orders</a></p>
        """,
    )


def send_new_order_email(to_emails: Iterable[str], order) -> None:
    """Notify admin-configured recipients of a newly confirmed order, with
    everything needed to plan the delivery: buyer, seller, address, and a
    per-product line-item breakdown."""
    e = html_lib.escape
    address = order.delivery_address or {}
    buyer = order.buyer
    shop = order.shop
    seller = shop.seller if shop else None

    address_lines = "<br>".join(
        e(part) for part in [
            address.get("exact_location"),
            address.get("ward"),
            address.get("subcounty"),
            address.get("town"),
            address.get("county"),
        ] if part
    )

    items_rows = "".join(
        f"""
        <tr>
            <td style="padding:6px 8px;border-bottom:1px solid #eee;">{e(item.product_snapshot.get('name', 'Product'))}</td>
            <td style="padding:6px 8px;border-bottom:1px solid #eee;">{e(item.product_snapshot.get('sku') or '-')}</td>
            <td style="padding:6px 8px;border-bottom:1px solid #eee;text-align:center;">{item.quantity}</td>
            <td style="padding:6px 8px;border-bottom:1px solid #eee;text-align:right;">KES {item.unit_price}</td>
            <td style="padding:6px 8px;border-bottom:1px solid #eee;text-align:right;">KES {item.line_total}</td>
        </tr>
        """
        for item in order.items
    )

    shop_location = ", ".join(filter(None, [e(shop.town) if shop and shop.town else None, e(shop.county) if shop and shop.county else None]))

    body_html = f"""
        <h2>New order #{str(order.id)[:8]}</h2>
        <p>Placed {order.created_at.strftime('%d %b %Y, %H:%M')} UTC</p>

        <h3>Buyer</h3>
        <p>
            {e(buyer.first_name)} {e(buyer.last_name)}<br>
            {e(buyer.phone) if buyer.phone else '-'}<br>
            {e(buyer.email)}
        </p>

        <h3>Delivery address</h3>
        <p>
            {e(address.get('first_name', buyer.first_name))} {e(address.get('last_name', buyer.last_name))}<br>
            {address_lines or '-'}<br>
            Phone: {e(address.get('phone') or buyer.phone or '-')}
        </p>

        <h3>Seller / shop</h3>
        <p>
            {e(shop.name) if shop else '-'}<br>
            {e(seller.phone) if seller and seller.phone else (e(shop.phone) if shop and shop.phone else '-')}<br>
            {shop_location or '-'}
        </p>

        <h3>Items</h3>
        <table style="border-collapse:collapse;width:100%;">
            <thead>
                <tr>
                    <th style="text-align:left;padding:6px 8px;border-bottom:2px solid #333;">Product</th>
                    <th style="text-align:left;padding:6px 8px;border-bottom:2px solid #333;">SKU</th>
                    <th style="text-align:center;padding:6px 8px;border-bottom:2px solid #333;">Qty</th>
                    <th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;">Unit price</th>
                    <th style="text-align:right;padding:6px 8px;border-bottom:2px solid #333;">Line total</th>
                </tr>
            </thead>
            <tbody>
                {items_rows}
            </tbody>
        </table>

        <h3>Totals</h3>
        <p>
            Subtotal: KES {order.subtotal}<br>
            Delivery fee: KES {order.delivery_fee}<br>
            <strong>Total: KES {order.total}</strong>
        </p>

        <p><a href="{settings.FRONTEND_URL}/admin">Open admin dashboard</a></p>
    """

    subject = f"New order #{str(order.id)[:8]} — {shop.name if shop else 'Ekshop'}"
    for to in to_emails:
        _send(to=to, subject=subject, html=body_html)
