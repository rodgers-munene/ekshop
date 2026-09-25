import uuid
from typing import Optional
from pydantic import BaseModel


class CountyRead(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class SubCountyRead(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class WardRead(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class WardWithLocationRead(BaseModel):
    id: uuid.UUID
    name: str
    subcounty_name: str
    county_name: str

    model_config = {"from_attributes": True}


class ReverseGeocodeRead(BaseModel):
    lat: float
    lng: float
    county: str
    subcounty: str
    ward: str
    location: Optional[str] = None
    sublocation: Optional[str] = None
    address_hint: str
    county_id: Optional[uuid.UUID] = None
    subcounty_id: Optional[uuid.UUID] = None
    ward_id: Optional[uuid.UUID] = None


class GeoSearchResult(BaseModel):
    type: str
    name: str
    subtitle: str
    lat: float
    lng: float
    county: Optional[str] = None
    subcounty: Optional[str] = None
    ward: Optional[str] = None
    location: Optional[str] = None
    sublocation: Optional[str] = None
