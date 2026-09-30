"""Schemas for partner fleet (3PL) integration."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.delivery import (
    PartnerFulfillmentMode,
    PartnerJobStatus,
    PartnerStatus,
)


# ── Partner fleets ─────────────────────────────────────────────────────────────


class PartnerFleetCreate(BaseModel):
    name: str
    slug: str
    api_base_url: Optional[str] = None
    # Write-only: never echoed back in responses.
    api_key: Optional[str] = None
    webhook_secret: Optional[str] = None
    auth_header_name: str = "Authorization"
    auth_header_prefix: str = "Bearer"
    supports_webhooks: bool = True
    timeout_seconds: int = Field(default=15, ge=1, le=120)
    base_pickup_fee: str = "0.00"
    per_km_fee: str = "0.00"
    per_kg_fee: str = "0.00"
    currency: str = "KES"
    coverage_counties: Optional[List[str]] = None
    notes: Optional[str] = None


class PartnerFleetUpdate(BaseModel):
    name: Optional[str] = None
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    webhook_secret: Optional[str] = None
    auth_header_name: Optional[str] = None
    auth_header_prefix: Optional[str] = None
    supports_webhooks: Optional[bool] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=120)
    base_pickup_fee: Optional[str] = None
    per_km_fee: Optional[str] = None
    per_kg_fee: Optional[str] = None
    currency: Optional[str] = None
    coverage_counties: Optional[List[str]] = None
    status: Optional[PartnerStatus] = None
    notes: Optional[str] = None


class PartnerFleetRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: PartnerStatus
    api_base_url: Optional[str]
    # Credentials are deliberately not exposed; this reports presence only.
    has_api_key: bool = False
    has_webhook_secret: bool = False
    auth_header_name: str
    auth_header_prefix: str
    supports_webhooks: bool
    timeout_seconds: int
    base_pickup_fee: str
    per_km_fee: str
    per_kg_fee: str
    currency: str
    coverage_counties: Optional[List[str]] = None
    success_rate: float
    avg_pickup_minutes: Optional[float]
    avg_delivery_minutes: Optional[float]
    total_jobs: int
    failed_jobs: int
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Partner jobs ───────────────────────────────────────────────────────────────


class PartnerJobCreate(BaseModel):
    delivery_id: uuid.UUID
    partner_id: uuid.UUID
    fulfillment_mode: PartnerFulfillmentMode = PartnerFulfillmentMode.same_city
    distance_km: float = Field(ge=0)
    weight_kg: float = Field(default=0.0, ge=0)
    # Set false to stage the job without calling the partner API.
    dispatch_immediately: bool = True


class PartnerJobRead(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    delivery_id: Optional[uuid.UUID]
    external_reference: Optional[str]
    partner_job_id: Optional[str]
    status: PartnerJobStatus
    fulfillment_mode: PartnerFulfillmentMode
    pickup_address: Dict[str, Any]
    pickup_lat: Optional[float]
    pickup_lng: Optional[float]
    drop_address: Dict[str, Any]
    drop_lat: Optional[float]
    drop_lng: Optional[float]
    distance_km: Optional[float]
    weight_kg: Optional[str]
    quoted_fee: Optional[str]
    partner_reported_fee: Optional[str]
    driver_name: Optional[str]
    driver_phone: Optional[str]
    vehicle_plate: Optional[str]
    failure_reason: Optional[str]
    dispatched_at: Optional[datetime]
    accepted_at: Optional[datetime]
    picked_up_at: Optional[datetime]
    in_transit_at: Optional[datetime]
    delivered_at: Optional[datetime]
    failed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PartnerJobListResponse(BaseModel):
    total: int
    page: int
    limit: int
    results: List[PartnerJobRead]


class PartnerQuoteRead(BaseModel):
    partner_id: uuid.UUID
    partner_name: str
    distance_km: float
    weight_kg: float
    quoted_fee: str
    currency: str
    estimated_ttl_minutes: float


class PartnerJobCancelRead(BaseModel):
    job: PartnerJobRead
    cancelled_at_partner: bool
    detail: Optional[str] = None


# ── Inbound webhooks ───────────────────────────────────────────────────────────


class PartnerWebhookRead(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    partner_job_id: Optional[str]
    event_type: str
    partner_event_id: Optional[str]
    signature_valid: bool
    processed_at: Optional[datetime]
    processing_error: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PartnerWebhookResultRead(BaseModel):
    accepted: bool
    signature_valid: bool
    applied: bool
    detail: Optional[str] = None
    event_id: str


class PartnerPerformanceRead(BaseModel):
    partner_id: str
    name: str
    status: str
    total_jobs: int
    status_breakdown: Dict[str, int]
    success_rate: Optional[float]
    avg_pickup_minutes: Optional[float]
    avg_delivery_minutes: Optional[float]
    total_quoted_cost: str
    total_partner_reported_cost: str