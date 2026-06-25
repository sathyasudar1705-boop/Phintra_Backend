import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.employee import Employee, EmployeeActivityEvent
from app.models.campaign import CampaignRecipient
from app.models.audit_log import SecurityScore

def log_activity_event(
    db: Session,
    employee_id: uuid.UUID,
    event_type: str,
    campaign_id: uuid.UUID = None,
    event_value: str = None
) -> EmployeeActivityEvent:
    """
    Log a behavior event, calculate point changes and risk changes,
    update employee risk score, and add audit log.
    """
    # 1. Fetch Employee
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        return None

    # Idempotency checks to prevent double scoring
    if campaign_id and event_type in ["email_sent", "email_opened", "link_clicked", "email_reported"]:
        exists = db.query(EmployeeActivityEvent).filter(
            EmployeeActivityEvent.campaign_id == campaign_id,
            EmployeeActivityEvent.employee_id == employee_id,
            EmployeeActivityEvent.event_type == event_type
        ).first()
        if exists:
            return exists

    if event_type == "training_completed" and event_value:
        exists = db.query(EmployeeActivityEvent).filter(
            EmployeeActivityEvent.employee_id == employee_id,
            EmployeeActivityEvent.event_type == event_type,
            EmployeeActivityEvent.event_value == event_value
        ).first()
        if exists:
            return exists

    if event_type == "quiz_passed" and event_value:
        exists = db.query(EmployeeActivityEvent).filter(
            EmployeeActivityEvent.employee_id == employee_id,
            EmployeeActivityEvent.event_type == event_type,
            EmployeeActivityEvent.event_value == event_value
        ).first()
        if exists:
            return exists

    # 2. Determine point and risk changes
    points_change = 0
    risk_change = 0

    if event_type == "email_sent":
        points_change = 0
        risk_change = 0
    elif event_type == "email_opened":
        points_change = -10
        risk_change = 10
    elif event_type == "link_clicked":
        points_change = -75  # Clicked without reporting initially
        risk_change = 25
    elif event_type == "email_reported":
        # Check if already clicked in this campaign
        has_clicked = False
        if campaign_id:
            cr = db.query(CampaignRecipient).filter(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.employee_id == employee_id
            ).first()
            if cr and (cr.clicked_at is not None or cr.status == "Clicked"):
                has_clicked = True

        if has_clicked:
            points_change = 125  # net +50 (-75 click + 125 = 50)
        else:
            points_change = 150  # reported before clicking
        risk_change = -20
    elif event_type == "training_completed":
        points_change = 50
        risk_change = -15
    elif event_type == "quiz_passed":
        points_change = 125  # Completed quiz (+50) + Passed quiz (+75)
        risk_change = -10
    elif event_type == "quiz_failed":
        points_change = -20
        risk_change = 0

    # 3. Create activity event log
    event = EmployeeActivityEvent(
        id=uuid.uuid4(),
        admin_id=emp.admin_id,
        company_id=emp.company_id,
        department_id=emp.department_id,
        employee_id=employee_id,
        campaign_id=campaign_id,
        event_type=event_type,
        event_value=event_value,
        points_change=points_change,
        risk_change=risk_change,
        created_at=datetime.utcnow()
    )
    db.add(event)

    # 4. Update employee risk score (clamped between 0.0 and 100.0)
    new_risk = max(0.0, min(100.0, emp.risk_score + risk_change))
    emp.risk_score = new_risk

    # 0-30 = Low risk, 31-70 = Medium risk, 71-100 = High risk
    if new_risk <= 30.0:
        emp.status = "Low Risk"
    elif new_risk <= 70.0:
        emp.status = "Medium Risk"
    else:
        emp.status = "High Risk"

    # Add security score audit log
    score_entry = SecurityScore(
        employee_id=emp.id,
        score=(100.0 - new_risk),
        recorded_at=datetime.utcnow()
    )
    db.add(score_entry)

    db.commit()
    return event
