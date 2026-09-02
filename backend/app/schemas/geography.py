import uuid
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
