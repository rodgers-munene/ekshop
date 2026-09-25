from sqlalchemy.orm import Session
from app.models.automation import AutomationSettings


def get_or_create_automation_settings(db: Session) -> AutomationSettings:
    settings = db.query(AutomationSettings).first()
    if settings:
        return settings

    settings = AutomationSettings()
    db.add(settings)
    db.flush()
    return settings
