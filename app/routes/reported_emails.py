from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.models.reported_email import ReportedEmail
from app.models.notification import Notification
from app.models.user import User
from app.schemas.reported_email_schema import (
    ReportedEmailCreate,
    ReportedEmailRead,
    ReportedEmailUpdate,
)
from app.utils.dependencies import get_current_admin

router = APIRouter(prefix="/reported-emails", tags=["Reported Emails"])

# POST /reported-emails
@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_report(report_in: ReportedEmailCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    # Verify employee exists
    employee = db.query(User).filter(User.id == report_in.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    # Create report
    new_report = ReportedEmail(
        employee_id=report_in.employee_id,
        employee_name=report_in.employee_name,
        employee_email=report_in.employee_email,
        campaign_id=report_in.campaign_id,
        campaign_name=report_in.campaign_name,
        email_subject=report_in.email_subject,
        sender_email=report_in.sender_email,
        email_body=report_in.email_body,
        threat_score=report_in.threat_score,
        report_reason=report_in.report_reason,
        report_status=report_in.report_status or "Pending",
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    # Create admin notification
    notif = Notification(
        user_id=None,
        employee_id=report_in.employee_id,
        title="New suspicious email reported",
        message=f"New suspicious email reported by {report_in.employee_name}",
    )
    db.add(notif)
    db.commit()

    return {"status": "reported", "report_id": str(new_report.id)}

# GET /reported-emails (paginated)
@router.get("", response_model=list[ReportedEmailRead])
def list_reports(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    reports = db.query(ReportedEmail).offset(skip).limit(limit).all()
    return reports

# GET /reported-emails/{id}
@router.get("/{report_id}", response_model=ReportedEmailRead)
def get_report(report_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin)):
    report = db.query(ReportedEmail).filter(ReportedEmail.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report

# PUT /reported-emails/{id}/review
@router.put("/{report_id}/review", response_model=ReportedEmailRead)
def review_report(
    report_id: UUID,
    update_in: ReportedEmailUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    report = db.query(ReportedEmail).filter(ReportedEmail.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.report_status = update_in.report_status
    report.reviewed_at = update_in.reviewed_at
    report.reviewed_by = update_in.reviewed_by
    db.commit()
    db.refresh(report)
    return report
