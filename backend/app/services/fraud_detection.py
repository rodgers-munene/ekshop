"""GPS Fraud Detection Service for Delivery Agents."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session

from app.models.delivery import (
    DeliveryAgent, Delivery, GPSFraudAlert, GPSFraudType, GPSFraudSeverity,
    DeliveryStatus,
)

logger = logging.getLogger(__name__)

# Configuration constants
MAX_REALISTIC_SPEED_KMH = 120  # Maximum realistic speed for delivery vehicles
MAX_ACCELERATION_KMH_PER_SEC = 15  # Maximum realistic acceleration
MIN_LOCATION_ACCURACY_M = 50  # Minimum GPS accuracy to trust (meters)
TELEPORTATION_THRESHOLD_KM = 5  # Distance that suggests teleportation
MIN_TIME_BETWEEN_UPDATES_SEC = 10  # Minimum time between location updates
STATIONARY_DRIFT_THRESHOLD_M = 100  # Drift while supposedly stationary


class GPSFraudDetectionService:
    """Detects GPS spoofing and fraudulent location reporting by delivery agents."""

    def __init__(self, db: Session):
        self.db = db

    def analyze_location_update(
        self,
        agent: DeliveryAgent,
        lat: float,
        lng: float,
        speed_kmh: Optional[float] = None,
        heading: Optional[float] = None,
        accuracy_m: Optional[float] = None,
        delivery_id: Optional[uuid.UUID] = None,
    ) -> List[GPSFraudAlert]:
        """Analyze a new location update for fraud indicators."""
        alerts = []

        # Get previous location
        prev_location = self._get_last_valid_location(agent.id)
        if not prev_location:
            # First location update, just store it
            return alerts

        prev_lat, prev_lng, prev_time, prev_speed = prev_location

        # Calculate time delta
        time_delta = (datetime.now(timezone.utc) - prev_time).total_seconds()
        if time_delta < MIN_TIME_BETWEEN_UPDATES_SEC:
            # Too frequent updates, could be spoofing
            alert = self._create_alert(
                agent=agent,
                delivery_id=delivery_id,
                fraud_type=GPSFraudType.gps_spoofing,
                severity=GPSFraudSeverity.low,
                lat=lat,
                lng=lng,
                speed_kmh=speed_kmh,
                heading=heading,
                accuracy_m=accuracy_m,
                expected_lat=prev_location[0],
                expected_lng=prev_location[1],
                distance_km=0,
                time_delta_sec=int(time_delta),
                speed_kmh=speed_kmh or 0,
                description=f"Location updates too frequent: {time_delta:.1f}s apart",
                evidence={"prev_time": prev_time.isoformat(), "current_time": datetime.now(timezone.utc).isoformat()},
            )
            alerts.append(alert)

        # Calculate distance and speed
        distance_km = self._haversine_distance(prev_location[0], prev_location[1], lat, lng)
        
        if time_delta > 0:
            calculated_speed = (distance_km / time_delta) * 3600  # km/h
            
            # Check for impossible speed
            if calculated_speed > MAX_REALISTIC_SPEED_KMH:
                alert = self._create_alert(
                    agent=agent,
                    delivery_id=delivery_id,
                    fraud_type=GPSFraudType.impossible_speed,
                    severity=GPSFraudSeverity.high,
                    lat=lat,
                    lng=lng,
                    speed_kmh=calculated_speed,
                    heading=heading,
                    accuracy_m=accuracy_m,
                    expected_lat=prev_location[0],
                    expected_lng=prev_location[1],
                    distance_km=distance_km,
                    time_delta_sec=int(time_delta),
                    speed_kmh=calculated_speed,
                    description=f"Impossible speed detected: {calculated_speed:.1f} km/h (max realistic: {MAX_REALISTIC_SPEED_KMH})",
                    evidence={
                        "prev_lat": prev_location[0],
                        "prev_lng": prev_location[1],
                        "prev_time": prev_location[2].isoformat(),
                        "calculated_speed": calculated_speed,
                        "max_allowed": MAX_REALISTIC_SPEED_KMH,
                    },
                )
                alerts.append(alert)

            # Check for teleportation (large distance in short time)
            if distance_km > TELEPORTATION_THRESHOLD_KM and time_delta < 300:  # 5km in <5 min
                alert = self._create_alert(
                    agent=agent,
                    delivery_id=delivery_id,
                    fraud_type=GPSFraudType.teleportation,
                    severity=GPSFraudSeverity.critical,
                    lat=lat,
                    lng=lng,
                    speed_kmh=calculated_speed,
                    heading=heading,
                    accuracy_m=accuracy_m,
                    expected_lat=prev_location[0],
                    expected_lng=prev_location[1],
                    distance_km=distance_km,
                    time_delta_sec=int(time_delta),
                    speed_kmh=calculated_speed,
                    description=f"Teleportation detected: {distance_km:.2f} km in {time_delta:.0f}s",
                    evidence={
                        "prev_lat": prev_location[0],
                        "prev_lng": prev_location[1],
                        "distance_km": distance_km,
                        "time_delta_sec": time_delta,
                    },
                )
                alerts.append(alert)

        # Check for stationary drift (agent claims to be moving but GPS drifts)
        if delivery_id:
            delivery = self.db.query(Delivery).filter(Delivery.id == delivery_id).first()
            if delivery and delivery.status == DeliveryStatus.picked:
                # Agent should be moving toward delivery
                if distance_km < 0.1 and time_delta > 300:  # <100m in 5+ minutes
                    alert = self._create_alert(
                        agent=agent,
                        delivery_id=delivery_id,
                        fraud_type=GPSFraudType.stationary_drift,
                        severity=GPSFraudSeverity.medium,
                        lat=lat,
                        lng=lng,
                        speed_kmh=speed_kmh or 0,
                        heading=heading,
                        accuracy_m=accuracy_m,
                        expected_lat=prev_location[0],
                        expected_lng=prev_location[1],
                        distance_km=distance_km,
                        time_delta_sec=int(time_delta),
                        speed_kmh=speed_kmh or 0,
                        description=f"Stationary drift: agent stationary for {time_delta/60:.0f}min during active delivery",
                        evidence={
                            "delivery_id": str(delivery_id),
                            "delivery_status": "picked",
                            "time_stationary_sec": time_delta,
                        },
                    )
                    alerts.append(alert)

        # Check accuracy - suspiciously perfect GPS
        if accuracy_m is not None and accuracy_m < 1.0:
            alert = self._create_alert(
                agent=agent,
                delivery_id=delivery_id,
                fraud_type=GPSFraudType.gps_spoofing,
                severity=GPSFraudSeverity.medium,
                lat=lat,
                lng=lng,
                speed_kmh=speed_kmh,
                heading=heading,
                accuracy_m=accuracy_m,
                expected_lat=lat,
                expected_lng=lng,
                distance_km=0,
                time_delta_sec=0,
                speed_kmh=0,
                description=f"Suspiciously perfect GPS accuracy: {accuracy_m}m",
                evidence={"accuracy_m": accuracy_m, "threshold": 1.0},
            )
            alerts.append(alert)

        # Save all alerts
        for alert in alerts:
            self.db.add(alert)
        if alerts:
            self.db.commit()

        return alerts

    def _get_last_valid_location(self, agent_id: uuid.UUID) -> Optional[Tuple[float, float, datetime, Optional[float]]]:
        """Get the last valid location update for an agent."""
        # This would typically come from a location history table
        # For now, use the agent's current location
        agent = self.db.query(DeliveryAgent).filter(DeliveryAgent.id == agent_id).first()
        if agent and agent.current_lat and agent.current_lng and agent.last_location_update:
            return (agent.current_lat, agent.current_lng, agent.last_location_update, None)
        return None

    def _create_alert(
        self,
        agent: DeliveryAgent,
        delivery_id: Optional[uuid.UUID],
        fraud_type: GPSFraudType,
        severity: GPSFraudSeverity,
        lat: float,
        lng: float,
        speed_kmh: Optional[float],
        heading: Optional[float],
        accuracy_m: Optional[float],
        expected_lat: float,
        expected_lng: float,
        distance_km: float,
        time_delta_sec: int,
        speed_kmh: float,
        description: str,
        evidence: dict,
    ) -> GPSFraudAlert:
        return GPSFraudAlert(
            agent_id=agent.id,
            delivery_id=delivery_id,
            fraud_type=fraud_type,
            severity=severity,
            lat=lat,
            lng=lng,
            speed_kmh=speed_kmh,
            heading=heading,
            accuracy_m=None,
            expected_lat=expected_lat,
            expected_lng=expected_lng,
            distance_km=distance_km,
            time_delta_sec=0,
            speed_kmh=speed_kmh,
            description=description,
            evidence=evidence,
        )

    def _haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points in km."""
        from math import radians, sin, cos, sqrt, atan2
        R = 6371
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = sin((lat2 - lat1) / 2)**2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2)**2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def detect_fraud_on_location_update(
    db: Session,
    agent: DeliveryAgent,
    lat: float,
    lng: float,
    speed_kmh: Optional[float] = None,
    heading: Optional[float] = None,
    accuracy_m: Optional[float] = None,
    delivery_id: Optional[uuid.UUID] = None,
) -> List[GPSFraudAlert]:
    """Convenience function to run fraud detection on location update."""
    service = GPSFraudDetectionService(db)
    return service.analyze_location_update(agent, lat, lng, speed_kmh, None, None, delivery_id)