import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.models.geography import County, SubCounty, Ward
from app.schemas.geography import CountyRead, SubCountyRead, WardRead

router = APIRouter(prefix="/geography", tags=["geography"])


@router.get("/counties", response_model=List[CountyRead])
def list_counties(db: Session = Depends(get_db)):
    return db.query(County).order_by(County.name).all()


@router.get("/counties/{county_name}/subcounties", response_model=List[SubCountyRead])
def list_subcounties(county_name: str, db: Session = Depends(get_db)):
    county = db.query(County).filter(County.name == county_name).first()
    if not county:
        raise HTTPException(404, "County not found")
    return (
        db.query(SubCounty)
        .filter(SubCounty.county_id == county.id)
        .order_by(SubCounty.name)
        .all()
    )


@router.get("/subcounties/{subcounty_id}/wards", response_model=List[WardRead])
def list_wards(subcounty_id: uuid.UUID, db: Session = Depends(get_db)):
    subcounty = db.query(SubCounty).filter(SubCounty.id == subcounty_id).first()
    if not subcounty:
        raise HTTPException(404, "Subcounty not found")
    return db.query(Ward).filter(Ward.subcounty_id == subcounty_id).order_by(Ward.name).all()
