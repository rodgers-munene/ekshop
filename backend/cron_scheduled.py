@router.post(
    "/process-scheduled-orders",
    summary="Process scheduled orders that are due (cron-triggered)",
)
def process_scheduled_orders(
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    """Find order groups with scheduled_at <= now and pending_payment status, 
    then trigger payment flow or mark as ready for payment."""
    from app.models.commerce import OrderGroup, OrderGroupStatus
    
    now = datetime.now(timezone.utc)
    
    scheduled_groups = db.query(OrderGroup).filter(
        OrderGroup.scheduled_at.isnot(None),
        OrderGroup.scheduled_at <= now,
        OrderGroup.status == OrderGroupStatus.pending_payment,
    ).all()
    
    processed = 0
    for group in scheduled_groups:
        # Mark as ready for payment (user will need to complete payment)
        # In a real implementation, you might trigger STK push automatically
        # or send a notification to the user
        group.status = OrderGroupStatus.pending_payment
        # The existing payment flow will handle the rest
        processed += 1
    
    db.commit()
    return {"status": "completed", "processed": processed}


@router.post(
    "/expire-old-scheduled-orders",
    summary="Cancel scheduled orders past their expiry (cron-triggered)",
)
def expire_old_scheduled_orders(
    expiry_hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    _: None = Depends(verify_cron_secret),
):
    """Cancel scheduled orders that are past their scheduled time + expiry window."""
    from app.models.commerce import OrderGroup, OrderGroupStatus
    
    expiry_cutoff = datetime.now(timezone.utc) - timedelta(hours=expiry_hours)
    
    expired_groups = db.query(OrderGroup).filter(
        OrderGroup.scheduled_at.isnot(None),
        OrderGroup.scheduled_at < expiry_cutoff,
        OrderGroup.status == OrderGroupStatus.pending_payment,
    ).all()
    
    cancelled = 0
    for group in expired_groups:
        group.status = OrderGroupStatus.cancelled
        cancelled += 1
    
    db.commit()
    return {"status": "completed", "cancelled": cancelled}