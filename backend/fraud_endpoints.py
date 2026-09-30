# GPS Fraud Detection Endpoints

@router.get(
    "/fraud/alerts",
    response_model=GPSFraudAlertListResponse,
    summary="List GPS fraud alerts (admin/ops)",
)
def list_gps_fraud_alerts(
    agent_id: Optional[uuid.UUID] = Query(None),
    fraud_type: Optional[GPSFraudType] = Query(None),
    severity: Optional[GPSFraudSeverity] = Query(None),
    is_reviewed: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(GPSFraudAlert)
    if agent_id:
        query = query.filter(GPSFraudAlert.agent_id == agent_id)
    if fraud_type:
        query = query.filter(GPSFraudAlert.fraud_type == fraud_type)
    if severity:
        query = query.filter(GPSFraudAlert.severity == severity)
    if is_reviewed is not None:
        query = query.filter(GPSFraudAlert.is_reviewed == is_reviewed)

    total = query.count()
    results = query.order_by(GPSFraudAlert.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return GPSFraudAlertListResponse(total=total, page=page, limit=limit, results=results)


@router.get(
    "/fraud/alerts/{alert_id}",
    response_model=GPSFraudAlertRead,
    summary="Get GPS fraud alert details",
)
def get_gps_fraud_alert(
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    alert = db.query(GPSFraudAlert).filter(GPSFraudAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Fraud alert not found")
    return alert


@router.patch(
    "/fraud/alerts/{alert_id}",
    response_model=GPSFraudAlertRead,
    summary="Review/resolve GPS fraud alert (admin/ops)",
)
def review_gps_fraud_alert(
    alert_id: uuid.UUID,
    payload: GPSFraudAlertReview,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    alert = db.query(GPSFraudAlert).filter(GPSFraudAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Fraud alert not found")

    alert.is_reviewed = True
    alert.resolution = payload.resolution
    alert.reviewed_at = datetime.now(timezone.utc)
    # In a real implementation, track who reviewed it

    db.commit()
    db.refresh(alert)
    return alert


@router.get(
    "/fraud/stats",
    response_model=dict,
    summary="Get GPS fraud detection statistics",
)
def get_gps_fraud_stats(
    period: Optional[str] = Query(None, pattern=PERIOD_PATTERN),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    since, until = _period_bounds(period, 30)

    alerts = db.query(GPSFraudAlert).filter(
        GPSFraudAlert.created_at >= since,
        GPSFraudAlert.created_at < until,
    ).all()

    stats = {
        "total": len(alerts),
        "by_type": {},
        "by_severity": {},
        "reviewed": 0,
        "pending_review": 0,
    }

    for alert in alerts:
        stats["by_type"][alert.fraud_type.value] = stats["by_type"].get(alert.fraud_type.value, 0) + 1
        stats["by_severity"][alert.severity.value] = stats["by_severity"].get(alert.severity.value, 0) + 1
        if alert.is_reviewed:
            stats["reviewed"] += 1
        else:
            stats["pending_review"] += 1

    return {
        "period": period or "last_30_days",
        **stats,
    }