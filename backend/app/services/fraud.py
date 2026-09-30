"""Order fraud detection and risk scoring service."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.commerce import OrderGroup


class FraudRiskLevel(str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FraudSignal:
    """Individual fraud signal with weight and description."""
    
    def __init__(self, name: str, weight: int, description: str):
        self.name = name
        self.weight = weight
        self.description = description


class FraudDetectionService:
    """Evaluates orders for fraud risk and returns a risk score."""

    # Risk thresholds
    LOW_THRESHOLD = 30
    MEDIUM_THRESHOLD = 60
    HIGH_THRESHOLD = 85

    def __init__(self, db: Session):
        self.db = db
        self.signals: list[FraudSignal] = []

    def evaluate_order(self, order_group: OrderGroup) -> dict:
        """Evaluate an order group for fraud risk."""
        self.signals = []
        score = 0

        # 1. Velocity checks
        score += self._check_velocity(order_group)
        
        # 2. New account check
        score += self._check_new_account(order_group)
        
        # 3. High-value order
        score += self._check_high_value(order_group)
        
        # 4. Multiple shops in single order
        score += self._check_multi_shop(order_group)
        
        # 5. Mismatched billing/shipping (if we had billing)
        score += self._check_address_mismatch(order_group)
        
        # 6. Known bad patterns (same IP, device - would need tracking)
        
        # 7. Payment method risks (M-Pesa vs card)
        
        # 8. Product category risks (electronics, gift cards)
        score += self._check_product_risk(order_group)

        # Determine risk level
        if score >= self.HIGH_THRESHOLD:
            risk_level = FraudRiskLevel.CRITICAL
        elif score >= self.MEDIUM_THRESHOLD:
            risk_level = FraudRiskLevel.HIGH
        elif score >= self.LOW_THRESHOLD:
            risk_level = FraudRiskLevel.MEDIUM
        else:
            risk_level = FraudRiskLevel.LOW

        return {
            "risk_score": min(score, 100),
            "risk_level": risk_level,
            "signals": [
                {"name": s.name, "weight": s.weight, "description": s.description}
                for s in self.signals
            ],
            "review_required": risk_level in (FraudRiskLevel.HIGH, FraudRiskLevel.CRITICAL),
            "auto_reject": risk_level == FraudRiskLevel.CRITICAL,
        }

    def _check_velocity(self, order_group: OrderGroup) -> int:
        """Check for rapid successive orders from same user."""
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_count = self.db.query(OrderGroup).filter(
            OrderGroup.buyer_id == order_group.buyer_id,
            OrderGroup.created_at >= since,
            OrderGroup.id != order_group.id,
        ).count()
        
        if recent_count >= 5:
            self.signals.append(FraudSignal("high_velocity_24h", 25, f"{recent_count} orders in last 24h"))
            return 25
        elif recent_count >= 3:
            self.signals.append(FraudSignal("elevated_velocity_24h", 10, f"{recent_count} orders in last 24h"))
            return 10
        return 0

    def _check_new_account(self, order_group: OrderGroup) -> int:
        """Check if buyer account is very new."""
        buyer = order_group.buyer
        account_age = datetime.now(timezone.utc) - buyer.created_at
        
        if account_age < timedelta(hours=1):
            self.signals.append(FraudSignal("brand_new_account", 30, "Account created less than 1 hour ago"))
            return 30
        elif account_age < timedelta(days=1):
            self.signals.append(FraudSignal("new_account_24h", 15, "Account created less than 24h ago"))
            return 15
        elif account_age < timedelta(days=7):
            self.signals.append(FraudSignal("new_account_week", 5, "Account created less than 7 days ago"))
            return 5
        return 0

    def _check_high_value(self, order_group: OrderGroup) -> int:
        """Check for unusually high order value."""
        from decimal import Decimal
        total = Decimal(order_group.total)
        
        # Get user's average order value
        avg = self.db.query(func.avg(OrderGroup.total.cast(Decimal))).filter(
            OrderGroup.buyer_id == order_group.buyer_id,
            OrderGroup.id != order_group.id,
            OrderGroup.status == "paid",
        ).scalar()
        
        if avg and total > Decimal(avg) * Decimal("5"):
            self.signals.append(FraudSignal("high_value_5x_avg", 20, f"Order value {total} is 5x user avg {avg}"))
            return 20
        elif total > Decimal("100000"):  # 100k KES
            self.signals.append(FraudSignal("high_value_absolute", 15, f"Order value {total} exceeds 100k KES"))
            return 15
        return 0

    def _check_multi_shop(self, order_group: OrderGroup) -> int:
        """Check for orders spanning many shops (potential reseller)."""
        shop_count = len({o.shop_id for o in order_group.orders})
        if shop_count >= 5:
            self.signals.append(FraudSignal("many_shops", 15, f"Order spans {shop_count} different shops"))
            return 15
        elif shop_count >= 3:
            self.signals.append(FraudSignal("several_shops", 5, f"Order spans {shop_count} shops"))
            return 5
        return 0

    def _check_address_mismatch(self, order_group: OrderGroup) -> int:
        """Check for billing/shipping mismatch (if we had billing addresses)."""
        # Placeholder - would need billing address model
        return 0

    def _check_product_risk(self, order_group: OrderGroup) -> int:
        """Check for high-risk product categories."""
        risky_categories = {"electronics", "phones", "gift cards", "vouchers"}
        for order in order_group.orders:
            for item in order.items:
                # Check product category name (simplified)
                if item.product and item.product.category:
                    cat_name = item.product.category.name.lower()
                    if any(risk in cat_name for risk in risky_categories):
                        self.signals.append(FraudSignal("high_risk_category", 10, f"Contains high-risk category: {cat_name}"))
                        return 10
        return 0


def evaluate_order_fraud(db: Session, order_group_id: uuid.UUID) -> dict:
    """Convenience function to evaluate a single order."""
    order_group = db.query(OrderGroup).filter(OrderGroup.id == order_group_id).first()
    if not order_group:
        return {"error": "Order not found"}
    return FraudDetectionService(db).evaluate_order(order_group)


def get_high_risk_orders(db: Session, limit: int = 50) -> list[dict]:
    """Get orders flagged for manual review."""
    # This is a simplified version - in production you'd store risk scores
    # and query them directly. For now, we evaluate recent orders.
    recent = db.query(OrderGroup).filter(
        OrderGroup.status == "paid",
        OrderGroup.created_at >= datetime.now(timezone.utc) - timedelta(days=7),
    ).limit(limit).all()
    
    results = []
    for og in recent:
        evaluation = FraudDetectionService(db).evaluate_order(og)
        if evaluation["risk_level"] in (FraudRiskLevel.HIGH, FraudRiskLevel.CRITICAL):
            results.append({
                "order_group_id": str(og.id),
                "buyer_id": str(og.buyer_id),
                "total": og.total,
                "created_at": og.created_at.isoformat(),
                **evaluation,
            })
    return results