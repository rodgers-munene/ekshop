with open(r'D:\EKSHOP-STORE\ekshop\backend\app\routers\delivery.py', 'r') as f:
    content = f.read()

new_end = '''

# Vehicle Requirements

@router.post(
    "/vehicle-requirements",
    response_model=VehicleRequirementRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a vehicle requirement (admin)",
)
def create_vehicle_requirement(
    payload: VehicleRequirementCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Create a vehicle requirement configuration."""
    req = VehicleRequirement(
        name=payload.name,
        required_vehicle_type=payload.required_vehicle_type,
        temperature_requirement=payload.temperature_requirement,
        min_capacity_kg=payload.min_capacity_kg,
        min_capacity_liters=payload.min_capacity_liters,
        requires_license=payload.requires_license,
        license_type=payload.license_type,
        special_features=payload.special_features,
        is_active=payload.is_active,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.get(
    "/vehicle-requirements",
    response_model=VehicleRequirementListResponse,
    summary="List vehicle requirements (admin)",
)
def list_vehicle_requirements(
    is_active: Optional[bool] = Query(None),
    vehicle_type: Optional[VehicleType] = Query(None),
    temperature: Optional[TemperatureRequirement] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(VehicleRequirement)
    if is_active is not None:
        query = query.filter(VehicleRequirement.is_active == is_active)
    if vehicle_type:
        query = query.filter(VehicleRequirement.required_vehicle_type == vehicle_type)
    if temperature:
        query = query.filter(VehicleRequirement.temperature_requirement == temperature)

    total = query.count()
    results = query.order_by(VehicleRequirement.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return VehicleRequirementListResponse(total=total, page=page, limit=limit, results=results)


@router.get(
    "/vehicle-requirements/{requirement_id}",
    response_model=VehicleRequirementRead,
    summary="Get a vehicle requirement",
)
def get_vehicle_requirement(
    requirement_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    req = db.query(VehicleRequirement).filter(VehicleRequirement.id == requirement_id).first()
    if not req:
        raise HTTPException(404, "Vehicle requirement not found")
    return req


@router.patch(
    "/vehicle-requirements/{requirement_id}",
    response_model=VehicleRequirementRead,
    summary="Update a vehicle requirement (admin)",
)
def update_vehicle_requirement(
    requirement_id: uuid.UUID,
    payload: VehicleRequirementUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    req = db.query(VehicleRequirement).filter(VehicleRequirement.id == requirement_id).first()
    if not req:
        raise HTTPException(404, "Vehicle requirement not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(req, field, value)

    db.commit()
    db.refresh(req)
    return req


@router.delete(
    "/vehicle-requirements/{requirement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a vehicle requirement (admin)",
)
def delete_vehicle_requirement(
    requirement_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    req = db.query(VehicleRequirement).filter(VehicleRequirement.id == requirement_id).first()
    if not req:
        raise HTTPException(404, "Vehicle requirement not found")
    db.delete(req)
    db.commit()
'''

# Read file and replace
with open(r'D:\EKSHOP-STORE\ekshop\backend\app\routers\delivery.py', 'r') as f:
    content = f.read()

# Find the last occurrence of the delete stop endpoint
idx = content.rfind('db.delete(stop)\n    db.commit()')
if idx >= 0:
    new_content = content[:idx + len('db.delete(stop)\n    db.commit()')] + new_end
    with open(r'D:\EKSHOP-STORE\ekshop\backend\app\routers\delivery.py', 'w') as f:
        f.write(new_content)
    print('Successfully replaced')
else:
    print('Pattern not found')