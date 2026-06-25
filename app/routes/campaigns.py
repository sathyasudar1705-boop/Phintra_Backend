from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.campaign import Campaign, CampaignRecipient, EmailTemplate, AwarenessPage, CampaignClick
from app.models.employee import Employee
from app.models.user import User
from app.schemas.campaign_schema import (
    CampaignCreate, CampaignUpdate, CampaignResponse, CampaignRecipientResponse,
    CampaignAssignRequest, EmailTemplateCreate, EmailTemplateUpdate, EmailTemplateResponse,
    AwarenessPageCreate, AwarenessPageUpdate, AwarenessPageResponse,
    CampaignClickCreate, CampaignAlertResponse, CampaignAnalyticsResponse,
    ClickedEmployeeInfo, NonClickedEmployeeInfo, DepartmentRiskInfo, ReportedEmployeeInfo
)
from app.services.email_service import send_email
from app.dependencies import require_manager, get_current_user, get_user_admin_id, get_user_company_id
from app.models.audit_log import AuditLog
from uuid import UUID
from typing import List
from app.config import settings

router = APIRouter(tags=["Campaigns"])

# =====================================================================
# CAMPAIGN ENDPOINTS
# =====================================================================

from app.models.department import Department

@router.get("/campaigns", response_model=List[CampaignResponse])
def list_campaigns(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """List all simulation campaigns with stats aggregates (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    campaigns = db.query(Campaign).filter((Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).all()
    results = []
    for c in campaigns:
        sent = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id).count()
        opened = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id, CampaignRecipient.status == "Opened").count()
        clicked = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id, CampaignRecipient.status == "Clicked").count()
        reported = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id, CampaignRecipient.status == "Reported").count()
        
        dept_name = "All Departments"
        if c.department_id:
            dept = db.query(Department).filter(Department.id == c.department_id).first()
            if dept:
                dept_name = dept.name
        else:
            first_recipient = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id).first()
            if first_recipient:
                emp = db.query(Employee).filter(Employee.id == first_recipient.employee_id).first()
                if emp:
                    dept = db.query(Department).filter(Department.id == emp.department_id).first()
                    if dept:
                        dept_name = dept.name
                        
        res = CampaignResponse.from_orm(c)
        res.sent = sent
        res.opened = opened
        res.clicked = clicked
        res.reported = reported
        res.department = dept_name
        res.employee_count = sent
        res.success_rate = round(((sent - clicked) / sent * 100.0), 2) if sent > 0 else 100.0
        res.date = c.launch_date.strftime("%Y-%m-%d") if c.launch_date else c.created_at.strftime("%Y-%m-%d")
        results.append(res)
    return results

@router.get("/campaigns/{id}", response_model=CampaignResponse)
def get_campaign(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Get details of campaign by UUID with stats aggregates (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    c = db.query(Campaign).filter(Campaign.id == id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    sent = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id).count()
    opened = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id, CampaignRecipient.status == "Opened").count()
    clicked = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id, CampaignRecipient.status == "Clicked").count()
    reported = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id, CampaignRecipient.status == "Reported").count()
    
    dept_name = "All Departments"
    if c.department_id:
        dept = db.query(Department).filter(Department.id == c.department_id).first()
        if dept:
            dept_name = dept.name
    else:
        first_recipient = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == c.id).first()
        if first_recipient:
            emp = db.query(Employee).filter(Employee.id == first_recipient.employee_id).first()
            if emp:
                dept = db.query(Department).filter(Department.id == emp.department_id).first()
                if dept:
                    dept_name = dept.name
                
    res = CampaignResponse.from_orm(c)
    res.sent = sent
    res.opened = opened
    res.clicked = clicked
    res.reported = reported
    res.department = dept_name
    res.employee_count = sent
    res.success_rate = round(((sent - clicked) / sent * 100.0), 2) if sent > 0 else 100.0
    res.date = c.launch_date.strftime("%Y-%m-%d") if c.launch_date else c.created_at.strftime("%Y-%m-%d")
    return res

@router.post("/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(camp_in: CampaignCreate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Create a new simulation campaign (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    
    name_val = camp_in.title if camp_in.title else camp_in.name
    type_val = camp_in.campaign_type if camp_in.campaign_type else camp_in.type
    
    if not name_val:
        raise HTTPException(status_code=400, detail="Campaign name or title is required")
        
    # Predefined / random sender profile assignment
    sender_profile_id = getattr(camp_in, "sender_profile_id", None)
    if not sender_profile_id:
        from app.models.sender_profile import SenderProfile
        import random
        all_profiles = db.query(SenderProfile).all()
        if all_profiles:
            sender_profile_id = random.choice(all_profiles).profile_id

    db_camp = Campaign(
        name=name_val,
        type=type_val if type_val else "Link Phishing",
        status=camp_in.status if camp_in.status else "Draft",
        launch_date=camp_in.launch_date,
        department_id=camp_in.department_id,
        template_id=camp_in.template_id,
        created_by=current_user.id,
        admin_id=admin_id,
        sender_profile_id=sender_profile_id
    )
    db.add(db_camp)
    db.commit()
    db.refresh(db_camp)
    
    # Assign employees if provided
    if camp_in.employee_ids:
        for emp_id in camp_in.employee_ids:
            emp = db.query(Employee).filter(
                Employee.id == emp_id,
                (Employee.company_id == company_id) | (Employee.admin_id == admin_id)
            ).first()
            if not emp:
                continue
            recipient = CampaignRecipient(campaign_id=db_camp.id, employee_id=emp_id)
            db.add(recipient)
        db.commit()
        db.refresh(db_camp)
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Campaign Creation", details=f"Created campaign: {db_camp.name}")
    db.add(audit)
    db.commit()
    return db_camp

@router.put("/campaigns/{id}", response_model=CampaignResponse)
def update_campaign(id: UUID, camp_in: CampaignUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Modify details of simulation campaign (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    camp = db.query(Campaign).filter(Campaign.id == id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    update_data = camp_in.dict(exclude_unset=True)
    
    # Map fields
    if "title" in update_data and update_data["title"]:
        camp.name = update_data["title"]
    if "name" in update_data and update_data["name"]:
        camp.name = update_data["name"]
        
    if "campaign_type" in update_data and update_data["campaign_type"]:
        camp.type = update_data["campaign_type"]
    if "type" in update_data and update_data["type"]:
        camp.type = update_data["type"]
        
    if "status" in update_data and update_data["status"]:
        camp.status = update_data["status"]
    if "launch_date" in update_data and update_data["launch_date"]:
        camp.launch_date = update_data["launch_date"]
    if "department_id" in update_data and update_data["department_id"]:
        camp.department_id = update_data["department_id"]
    if "template_id" in update_data:
        camp.template_id = update_data["template_id"]
        
    db.commit()
    db.refresh(camp)
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Campaign Modification", details=f"Modified campaign: {camp.name}")
    db.add(audit)
    db.commit()
    return camp

def personalize_content(text: str, employee_name: str, company_name: str, tracking_link: str) -> str:
    if not text:
        return text
    # Replace new tokens
    text = text.replace("{{EmployeeName}}", employee_name)
    text = text.replace("{{Company}}", company_name)
    text = text.replace("{{TrackingLink}}", tracking_link)
    # Replace legacy tokens
    text = text.replace("{{employee_name}}", employee_name)
    text = text.replace("{{company_name}}", company_name)
    text = text.replace("{{login_link}}", tracking_link)
    return text

@router.post("/campaigns/{id}/send-test")
def send_campaign_test_email(id: UUID, req: dict, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Send a single test email of the campaign to the admin/manager email."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    camp = db.query(Campaign).filter(Campaign.id == id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    test_email = req.get("test_email")
    if not test_email:
        raise HTTPException(status_code=400, detail="test_email is required")
        
    # Retrieve template
    if not camp.template_id:
        template = db.query(EmailTemplate).filter((EmailTemplate.admin_id == admin_id) | (EmailTemplate.admin_id == None)).first()
    else:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == camp.template_id).first()
        
    if not template:
        raise HTTPException(status_code=400, detail="No email template is configured for this campaign")
        
    # Reconstruct body & subject
    subject = template.subject
    body = template.body_html or template.body_text or ""
    import json
    try:
        template_data = json.loads(body)
        body = template_data.get("body", body)
    except Exception:
        pass
        
    import uuid
    tracking_link = f"{settings.FRONTEND_URL}/report/{uuid.uuid4()}"
    personalized_subject = personalize_content(subject, "Test Recipient", "Phintra Test Lab", tracking_link)
    personalized_body = personalize_content(body, "Test Recipient", "Phintra Test Lab", tracking_link)
    
    success = send_email(db, test_email, f"[TEST] {personalized_subject}", personalized_body)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send test SMTP email. Check SMTP settings in .env.")
        
    return {"status": "success", "message": f"Test email sent to {test_email}"}

@router.post("/campaigns/{id}/launch")
def launch_campaign_route(id: UUID, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Launch/deploy the campaign: set active, send emails to all recipients (Managers & Admins)."""
    from datetime import datetime
    from app.utils.scoring import log_activity_event
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    camp = db.query(Campaign).filter(Campaign.id == id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    camp.status = "Active"
    camp.launch_date = datetime.utcnow()
    
    # Retrieve template
    if not camp.template_id:
        template = db.query(EmailTemplate).filter((EmailTemplate.admin_id == admin_id) | (EmailTemplate.admin_id == None)).first()
    else:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == camp.template_id).first()
        
    if not template:
        raise HTTPException(status_code=400, detail="No email template is configured for this campaign")
        
    # Get all recipients
    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == id).all()
    
    sent_count = 0
    failed_count = 0
    
    # Fetch sender profile if assigned
    sender_profile = None
    if camp.sender_profile_id:
        from app.models.sender_profile import SenderProfile
        sender_profile = db.query(SenderProfile).filter(SenderProfile.profile_id == camp.sender_profile_id).first()

    for r in recipients:
        emp = db.query(Employee).filter(
            Employee.id == r.employee_id,
            (Employee.company_id == company_id) | (Employee.admin_id == admin_id)
        ).first()
        if not emp:
            continue
            
        # Populate tenant/isolation fields and timestamps
        r.admin_id = emp.admin_id
        r.company_id = emp.company_id
        r.department_id = emp.department_id
        r.sent_at = datetime.utcnow()
        r.delivered_at = datetime.utcnow()

        # Ensure track_id is set
        if not r.track_id:
            import uuid
            r.track_id = uuid.uuid4()
            
        # Personalize tracking link
        tracking_link = f"{settings.FRONTEND_URL}/report/{r.track_id}"
        
        subject = template.subject
        body = template.body_html or template.body_text or ""
        import json
        try:
            template_data = json.loads(body)
            body = template_data.get("body", body)
        except Exception:
            pass
            
        # Personalize placeholders
        employee_name = f"{emp.first_name} {emp.last_name}" if (emp.first_name or emp.last_name) else (emp.name or "Valued Employee")
        company_name = "Phintra Enterprise"
        if emp.company and emp.company.company_name:
            company_name = emp.company.company_name
            
        personalized_subject = personalize_content(subject, employee_name, company_name, tracking_link)
        personalized_body = personalize_content(body, employee_name, company_name, tracking_link)
        
        # Inject open tracking pixel dynamically using request base URL
        open_pixel_url = f"{request.base_url}campaigns/open/{r.track_id}"
        personalized_body += f'<img src="{open_pixel_url}" width="1" height="1" style="display:none;" />'

        success = send_email(
            db,
            emp.email,
            personalized_subject,
            personalized_body,
            campaign_id=camp.id,
            template_id=template.id,
            employee_id=emp.id,
            admin_id=admin_id,
            sender_profile=sender_profile
        )
        if success:
            r.status = "Sent"
            sent_count += 1
            
            # Log email_sent event
            log_activity_event(db, emp.id, "email_sent", campaign_id=camp.id)

            # Compliance audit log for each email send mapping
            send_audit = AuditLog(
                user_id=current_user.id,
                action="Simulation Email Dispatched",
                details=(
                    f"Dispatched simulation to {emp.email} (Campaign: '{camp.name}' ID: {camp.id}). "
                    f"Template ID: {template.id}, Title: '{template.title}', Subject: '{personalized_subject}'. "
                    f"Tokens replaced: {{EmployeeName}} -> '{employee_name}', "
                    f"{{Company}} -> '{company_name}', {{TrackingLink}} -> '{tracking_link}'."
                )
            )
            db.add(send_audit)
        else:
            r.status = "Failed"
            failed_count += 1
            
    db.commit()
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Campaign Launch", details=f"Launched campaign '{camp.name}' (Sent: {sent_count}, Failed: {failed_count})")
    db.add(audit)
    db.commit()
    
    return {"message": f"Campaign launched successfully. {sent_count} emails sent, {failed_count} failed."}


@router.delete("/campaigns/{id}", status_code=status.HTTP_200_OK)
def delete_campaign(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Delete simulation campaign (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    camp = db.query(Campaign).filter(Campaign.id == id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    camp_name = camp.name
    db.delete(camp)
    db.commit()
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Campaign Deletion", details=f"Deleted campaign: {camp_name}")
    db.add(audit)
    db.commit()
    return {"detail": "Campaign successfully deleted"}

@router.post("/campaigns/{id}/archive", response_model=CampaignResponse)
def archive_campaign_route(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Archive simulation campaign (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    camp = db.query(Campaign).filter(Campaign.id == id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    camp.status = "Archived"
    db.commit()
    db.refresh(camp)
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Campaign Archival", details=f"Archived campaign: {camp.name}")
    db.add(audit)
    db.commit()
    return camp

@router.post("/campaigns/{id}/remind")
def send_campaign_reminder_route(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Dispatch reminder email via SMTP to campaign recipients (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    camp = db.query(Campaign).filter(Campaign.id == id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == id).all()
    if not recipients:
        raise HTTPException(status_code=400, detail="No employees assigned to this campaign")
        
    # Find template
    template = db.query(EmailTemplate).first()
    subject = f"Reminder: {template.subject}" if template else f"Phintra Platform Reminder: {camp.name}"
    body = f"<h3>Reminder Notice</h3><p>Please complete your compliance awareness modules related to: <b>{camp.name}</b></p>"
    if template:
        import json
        try:
            template_data = json.loads(template.body_html)
            body_content = template_data.get("body", template.body_html)
        except Exception:
            body_content = template.body_html
        body += f"<hr>{body_content}"
        
    sent_count = 0
    # Fetch sender profile if assigned
    sender_profile = None
    if camp.sender_profile_id:
        from app.models.sender_profile import SenderProfile
        sender_profile = db.query(SenderProfile).filter(SenderProfile.profile_id == camp.sender_profile_id).first()

    for r in recipients:
        emp = db.query(Employee).filter(
            Employee.id == r.employee_id,
            (Employee.company_id == company_id) | (Employee.admin_id == admin_id)
        ).first()
        if emp:
            success = send_email(db, emp.email, subject, body)
            if success:
                sent_count += 1
                
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Campaign Reminder Dispatch", details=f"Sent {sent_count} reminders for campaign: {camp.name}")
    db.add(audit)
    db.commit()
    return {"message": f"Successfully sent {sent_count} reminder emails."}

@router.get("/campaigns/{id}/recipients")
def list_campaign_recipients(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """List recipients of a simulation campaign (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    # Verify campaign belongs to admin
    camp = db.query(Campaign).filter(Campaign.id == id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == id).all()
    results = []
    # Fetch sender profile if assigned
    sender_profile = None
    if camp.sender_profile_id:
        from app.models.sender_profile import SenderProfile
        sender_profile = db.query(SenderProfile).filter(SenderProfile.profile_id == camp.sender_profile_id).first()

    for r in recipients:
        emp = db.query(Employee).filter(
            Employee.id == r.employee_id,
            (Employee.company_id == company_id) | (Employee.admin_id == admin_id)
        ).first()
        if emp:
            results.append({
                "employee_id": str(r.employee_id),
                "name": f"{emp.first_name} {emp.last_name}",
                "email": emp.email,
                "status": r.status
            })
    return results

@router.post("/campaigns/{id}/assign-employees", response_model=List[CampaignRecipientResponse])
def assign_recipients(id: UUID, req: CampaignAssignRequest, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Bind employee targets to simulation campaign (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    camp = db.query(Campaign).filter(Campaign.id == id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    results = []
    for emp_id in req.employee_ids:
        # Verify employee exists and belongs to this admin
        emp = db.query(Employee).filter(
            Employee.id == emp_id,
            (Employee.company_id == company_id) | (Employee.admin_id == admin_id)
        ).first()
        if not emp:
            continue
        # Verify not already assigned
        existing = db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == id,
            CampaignRecipient.employee_id == emp_id
        ).first()
        if existing:
            results.append(existing)
            continue
            
        recipient = CampaignRecipient(campaign_id=id, employee_id=emp_id)
        db.add(recipient)
        results.append(recipient)
        
    db.commit()
    # Refresh all
    for r in results:
        db.refresh(r)
        
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Campaign Recipient Assignment", details=f"Assigned {len(results)} recipients to campaign: {camp.name}")
    db.add(audit)
    db.commit()
    return results

@router.post("/campaigns/{id}/send-awareness-email")
def trigger_awareness_emails(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Trigger SMTP dispatch of security awareness email to all campaign recipients (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    camp = db.query(Campaign).filter(Campaign.id == id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == id).all()
    if not recipients:
        raise HTTPException(status_code=400, detail="No employees assigned to this campaign")
        
    # Pick a template (or generate default training content)
    template = db.query(EmailTemplate).first()
    subject = template.subject if template else f"Phintra Platform Security Alert: {camp.name}"
    body = f"<h3>Phintra Awareness Platform</h3><p>Authorized training test for campaign: <b>{camp.name}</b></p>"
    if template:
        import json
        try:
            template_data = json.loads(template.body_html)
            body = template_data.get("body", template.body_html)
        except Exception:
            body = template.body_html
    
    sent_count = 0
    failed_count = 0
    for recipient in recipients:
        emp = db.query(Employee).filter(
            Employee.id == recipient.employee_id,
            (Employee.company_id == company_id) | (Employee.admin_id == admin_id)
        ).first()
        if not emp:
            continue
            
        success = send_email(db, emp.email, subject, body, admin_id=admin_id)
        if success:
            recipient.status = "Sent"
            sent_count += 1
        else:
            recipient.status = "Failed"
            failed_count += 1
            
    db.commit()
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Campaign SMTP Dispatch", details=f"Dispatched simulation emails for campaign: {camp.name} (Success: {sent_count}, Fail: {failed_count})")
    db.add(audit)
    db.commit()
    
    return {
        "detail": "Campaign emails dispatched",
        "total_recipients": len(recipients),
        "sent_successfully": sent_count,
        "failed_sends": failed_count
    }


# =====================================================================
# EMAIL TEMPLATE ENDPOINTS
# =====================================================================

import re

def validate_sender_domain(email_or_domain: str, db: Session, admin_id: UUID):
    if not email_or_domain:
        return
    # Extract domain
    domain = email_or_domain.split("@")[-1].lower() if "@" in email_or_domain else email_or_domain.lower()
    
    # List of blocked real major domains (impersonation targets)
    blocked_domains = {
        "google.com", "microsoft.com", "apple.com", "amazon.com", "netflix.com", 
        "paypal.com", "facebook.com", "github.com", "linkedin.com", "zoom.us",
        "chase.com", "bankofamerica.com", "wellsfargo.com", "citibank.com",
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com"
    }
    
    if domain in blocked_domains:
        raise HTTPException(
            status_code=400,
            detail=f"Domain '{domain}' is a restricted public or company domain. Impersonation of major brand domains is blocked."
        )
        
    # Get the admin's company email domain
    from app.models.company import Company
    company = db.query(Company).filter(Company.admin_id == admin_id).first()
    if company and company.company_email:
        comp_domain = company.company_email.split("@")[-1].lower()
        if domain == comp_domain:
            raise HTTPException(
                status_code=400,
                detail=f"Domain '{domain}' is your company's official domain. Phishing simulations cannot send from unauthorized real corporate domains to prevent real spoofing/spam filters from blocking."
            )

def check_sensitive_content(text: str):
    if not text:
        return
    # Check for input elements or forms that collect credentials
    input_pattern = re.compile(r'<input\s+[^>]*type=["\']?password["\']?[^>]*>', re.IGNORECASE)
    if input_pattern.search(text):
        raise HTTPException(
            status_code=400,
            detail="Templates cannot contain password input fields to prevent sensitive credential collection."
        )
    
    form_pattern = re.compile(r'<form\s+[^>]*>', re.IGNORECASE)
    if form_pattern.search(text):
        raise HTTPException(
            status_code=400,
            detail="Templates cannot contain form elements to prevent credential collection."
        )

    # Keyword blocklist (case insensitive) for sensitive PII or authentication details
    forbidden_keywords = [
        "otp", "one-time password", "one time password", "social security number", "ssn", 
        "credit card number", "cvv", "bank account number", "pin number"
    ]
    
    lower_text = text.lower()
    for keyword in forbidden_keywords:
        if keyword in lower_text:
            raise HTTPException(
                status_code=400,
                detail=f"Template contains restricted keyword/topic: '{keyword}'. Phintra simulations are prohibited from collecting passwords, OTPs, bank details, or sensitive PII."
            )

@router.get("/email-templates", response_model=List[EmailTemplateResponse])
def list_email_templates(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """List simulation email templates (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    return db.query(EmailTemplate).filter((EmailTemplate.admin_id == admin_id) | (EmailTemplate.admin_id == None)).all()

@router.post("/email-templates", response_model=EmailTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_email_template(temp_in: EmailTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Create simulation email template (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    
    title = temp_in.template_name or temp_in.title or "Untitled Template"
    sender_name = temp_in.sender_display_name or temp_in.sender_name or "System Notification"
    sender_email = temp_in.sender_email
    body_html = temp_in.body_html
    body_text = temp_in.body_text
    subject = temp_in.subject
    
    # Run validations
    validate_sender_domain(sender_email, db, admin_id)
    check_sensitive_content(subject)
    check_sensitive_content(body_html)
    check_sensitive_content(body_text)
    
    db_temp = EmailTemplate(
        admin_id=admin_id,
        title=title,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        category=temp_in.category,
        difficulty=temp_in.difficulty,
        sender_name=sender_name,
        sender_email=sender_email
    )
    db.add(db_temp)
    db.commit()
    db.refresh(db_temp)
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Template Created", details=f"Created template '{title}' (ID: {db_temp.id})")
    db.add(audit)
    db.commit()
    
    return db_temp

@router.put("/email-templates/{id}", response_model=EmailTemplateResponse)
def update_email_template(id: UUID, temp_in: EmailTemplateUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Update simulation email template (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    temp = db.query(EmailTemplate).filter(EmailTemplate.id == id, (EmailTemplate.admin_id == admin_id) | (EmailTemplate.admin_id == None)).first()
    if not temp:
        raise HTTPException(status_code=404, detail="Template not found or unauthorized")
        
    update_data = temp_in.dict(exclude_unset=True)
    
    # Validate sender domain
    if "sender_email" in update_data:
        validate_sender_domain(update_data["sender_email"], db, admin_id)
        
    # Validate sensitive content
    for field in ["subject", "body_html", "body_text"]:
        if field in update_data:
            check_sensitive_content(update_data[field])

    # Resolve names
    if "template_name" in update_data:
        update_data["title"] = update_data.pop("template_name")
    if "sender_display_name" in update_data:
        update_data["sender_name"] = update_data.pop("sender_display_name")
        
    for key, val in update_data.items():
        setattr(temp, key, val)
        
    db.commit()
    db.refresh(temp)
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Template Updated", details=f"Updated template '{temp.title}' (ID: {temp.id})")
    db.add(audit)
    db.commit()
    
    return temp

@router.post("/email-templates/{id}/clone", response_model=EmailTemplateResponse, status_code=status.HTTP_201_CREATED)
def clone_email_template(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Clone/duplicate an existing email template (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    temp = db.query(EmailTemplate).filter(EmailTemplate.id == id, (EmailTemplate.admin_id == admin_id) | (EmailTemplate.admin_id == None)).first()
    if not temp:
        raise HTTPException(status_code=404, detail="Template not found")
        
    cloned_temp = EmailTemplate(
        admin_id=admin_id,
        title=f"Copy of {temp.title}",
        subject=temp.subject,
        body_html=temp.body_html,
        body_text=temp.body_text,
        category=temp.category,
        difficulty=temp.difficulty,
        sender_name=temp.sender_name,
        sender_email=temp.sender_email
    )
    db.add(cloned_temp)
    db.commit()
    db.refresh(cloned_temp)
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Template Cloned", details=f"Cloned template '{temp.title}' as '{cloned_temp.title}' (ID: {cloned_temp.id})")
    db.add(audit)
    db.commit()
    
    return cloned_temp

@router.delete("/email-templates/{id}", status_code=status.HTTP_200_OK)
def delete_email_template(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Delete simulation email template (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    temp = db.query(EmailTemplate).filter(EmailTemplate.id == id, (EmailTemplate.admin_id == admin_id) | (EmailTemplate.admin_id == None)).first()
    if not temp:
        raise HTTPException(status_code=404, detail="Template not found or unauthorized")
    db.delete(temp)
    db.commit()
    return {"detail": "Email template successfully deleted"}



# =====================================================================
# AWARENESS PAGE ENDPOINTS
# =====================================================================

@router.get("/awareness-pages", response_model=List[AwarenessPageResponse])
def list_awareness_pages(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """List warning awareness landing pages (Managers & Admins)."""
    return db.query(AwarenessPage).all()

@router.post("/awareness-pages", response_model=AwarenessPageResponse, status_code=status.HTTP_201_CREATED)
def create_awareness_page(page_in: AwarenessPageCreate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Create warning awareness landing page (Managers & Admins)."""
    db_page = AwarenessPage(**page_in.dict())
    db.add(db_page)
    db.commit()
    db.refresh(db_page)
    return db_page

@router.put("/awareness-pages/{id}", response_model=AwarenessPageResponse)
def update_awareness_page(id: UUID, page_in: AwarenessPageUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Modify details of warning awareness landing page (Managers & Admins)."""
    page = db.query(AwarenessPage).filter(AwarenessPage.id == id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Awareness page not found")
        
    update_data = page_in.dict(exclude_unset=True)
    for key, val in update_data.items():
        setattr(page, key, val)
        
    db.commit()
    db.refresh(page)
    return page

@router.delete("/awareness-pages/{id}", status_code=status.HTTP_200_OK)
def delete_awareness_page(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Delete warning awareness landing page (Managers & Admins)."""
    page = db.query(AwarenessPage).filter(AwarenessPage.id == id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Awareness page not found")
    db.delete(page)
    db.commit()
    return {"detail": "Awareness page successfully deleted"}


# =====================================================================
# CLICK TRACKING & ANALYTICS ENDPOINTS
# =====================================================================

@router.get("/campaigns/open/{track_id}", response_class=Response)
def record_campaign_open(track_id: UUID, db: Session = Depends(get_db)):
    """Record email open tracking pixel and update campaign recipient status."""
    from fastapi import Response
    from datetime import datetime
    from app.utils.scoring import log_activity_event
    
    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.track_id == track_id).first()
    if recipient:
        if recipient.status in ["Sent", "Delivered"]:
            recipient.opened_at = datetime.utcnow()
            recipient.status = "Opened"
            db.commit()
            
            # Log event
            log_activity_event(db, recipient.employee_id, "email_opened", campaign_id=recipient.campaign_id)
            
    # Return a 1x1 transparent PNG image
    transparent_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
    return Response(transparent_png, media_type="image/png")


@router.get("/campaigns/click/{track_id}", response_class=RedirectResponse)
def record_campaign_click_get(track_id: UUID, request: Request, db: Session = Depends(get_db)):
    """Record click event via GET and redirect to the frontend awareness page."""
    from datetime import datetime
    from app.utils.scoring import log_activity_event
    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.track_id == track_id).first()
    if recipient:
        campaign = db.query(Campaign).filter(Campaign.id == recipient.campaign_id).first()
        employee = db.query(Employee).filter(Employee.id == recipient.employee_id).first()
        if campaign and employee:
            already_clicked = db.query(CampaignClick).filter(
                CampaignClick.campaign_id == campaign.id,
                CampaignClick.employee_id == employee.id,
                CampaignClick.track_id == track_id
            ).first()
            
            user_agent = request.headers.get("User-Agent", "Unknown")
            ip_address = request.client.host if request.client else "127.0.0.1"
            
            if not already_clicked:
                click = CampaignClick(
                    admin_id=employee.admin_id if employee.admin_id else campaign.created_by,
                    campaign_id=campaign.id,
                    employee_id=employee.id,
                    email=employee.email,
                    track_id=track_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="Clicked"
                )
                db.add(click)
                
                recipient.status = "Clicked"
                recipient.clicked_at = datetime.utcnow()
                
                from app.models.email_log import EmailLog
                db.query(EmailLog).filter(
                    EmailLog.campaign_id == campaign.id,
                    EmailLog.employee_id == employee.id
                ).update({"status": "Clicked"}, synchronize_session=False)
                
                # Use log_activity_event for behavioral score updates
                log_activity_event(db, employee.id, "link_clicked", campaign_id=campaign.id)
                
                db.commit()
                
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/report/{track_id}")

def record_campaign_click_get_old(track_id: UUID, request: Request, db: Session = Depends(get_db)):
    """Record click event via GET and serve a beautiful awareness landing page."""
    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.track_id == track_id).first()
    if not recipient:
        return HTMLResponse(content="<h1>Invalid link</h1><p>This tracking code is invalid or expired.</p>", status_code=404)
        
    campaign = db.query(Campaign).filter(Campaign.id == recipient.campaign_id).first()
    employee = db.query(Employee).filter(Employee.id == recipient.employee_id).first()
    if not campaign or not employee:
        return HTMLResponse(content="<h1>Record not found</h1><p>Associated records not found.</p>", status_code=404)
        
    already_clicked = db.query(CampaignClick).filter(
        CampaignClick.campaign_id == campaign.id,
        CampaignClick.employee_id == employee.id,
        CampaignClick.track_id == track_id
    ).first()
    
    user_agent = request.headers.get("User-Agent", "Unknown")
    ip_address = request.client.host if request.client else "127.0.0.1"
    
    if not already_clicked:
        click = CampaignClick(
            admin_id=employee.admin_id if employee.admin_id else campaign.created_by,
            campaign_id=campaign.id,
            employee_id=employee.id,
            email=employee.email,
            track_id=track_id,
            ip_address=ip_address,
            user_agent=user_agent,
            status="Clicked"
        )
        db.add(click)
        recipient.status = "Clicked"
        
        from app.models.email_log import EmailLog
        db.query(EmailLog).filter(
            EmailLog.campaign_id == campaign.id,
            EmailLog.employee_id == employee.id
        ).update({"status": "Clicked"}, synchronize_session=False)
        
        # Adjust employee risk rating upwards on simulated failure
        employee.risk_score = min(100.0, employee.risk_score + 20.0)
        if employee.risk_score < 20.0:
            employee.status = "Low Risk"
        elif employee.risk_score < 50.0:
            employee.status = "Medium Risk"
        elif employee.risk_score < 80.0:
            employee.status = "High Risk"
        else:
            employee.status = "Critical"
            
        from app.models.audit_log import SecurityScore
        score_entry = SecurityScore(employee_id=employee.id, score=(100.0 - employee.risk_score))
        db.add(score_entry)
        
        db.commit()
    
    template_subject = "Suspicious Phishing Email"
    template_sender = "unknown@sender.com"
    if campaign.template_id:
        tpl = db.query(EmailTemplate).filter(EmailTemplate.id == campaign.template_id).first()
        if tpl:
            template_subject = tpl.subject
            try:
                import json
                tpl_data = json.loads(tpl.body_html)
                template_sender = tpl_data.get("sender_email", "unknown@sender.com")
            except Exception:
                template_sender = "unknown@sender.com"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Phishing Simulation Interception</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --color-danger: #ef4444;
                --color-danger-light: #fee2e2;
                --bg-card: #ffffff;
                --text-main: #111827;
                --text-muted: #4b5563;
                --border-color: #e5e7eb;
            }}
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            body {{
                font-family: 'Inter', sans-serif;
                background-color: #f9fafb;
                color: var(--text-main);
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                padding: 24px;
            }}
            .card {{
                background-color: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                max-width: 600px;
                width: 100%;
                overflow: hidden;
            }}
            .banner {{
                background-color: var(--color-danger-light);
                border-bottom: 4px solid var(--color-danger);
                padding: 32px 24px;
                text-align: center;
            }}
            .icon-wrapper {{
                background-color: var(--color-danger);
                color: white;
                width: 56px;
                height: 56px;
                border-radius: 50%;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                font-size: 28px;
                font-weight: bold;
                margin-bottom: 16px;
                box-shadow: 0 4px 6px -1px rgba(239, 68, 68, 0.4);
            }}
            h1 {{
                font-size: 24px;
                font-weight: 800;
                color: #991b1b;
                margin-bottom: 8px;
            }}
            .banner p {{
                color: #b91c1c;
                font-weight: 600;
                font-size: 15px;
            }}
            .content {{
                padding: 32px 24px;
            }}
            .intro-text {{
                font-size: 15px;
                line-height: 1.6;
                color: var(--text-muted);
                margin-bottom: 24px;
            }}
            .details-box {{
                background-color: #f3f4f6;
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 24px;
            }}
            .details-title {{
                font-weight: 700;
                font-size: 13px;
                color: var(--text-main);
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 12px;
            }}
            .details-row {{
                display: flex;
                justify-content: space-between;
                font-size: 13px;
                padding: 6px 0;
                border-bottom: 1px solid #e5e7eb;
            }}
            .details-row:last-child {{
                border-bottom: none;
            }}
            .details-label {{
                color: var(--text-muted);
            }}
            .details-val {{
                font-weight: 600;
                color: var(--text-main);
            }}
            h2 {{
                font-size: 16px;
                font-weight: 700;
                margin-bottom: 12px;
                color: var(--text-main);
            }}
            ul {{
                list-style-position: inside;
                margin-left: 4px;
                margin-bottom: 24px;
            }}
            li {{
                font-size: 14px;
                color: var(--text-muted);
                line-height: 1.6;
                margin-bottom: 8px;
            }}
            .btn {{
                display: block;
                width: 100%;
                text-align: center;
                background-color: #2563eb;
                color: white;
                text-decoration: none;
                font-weight: 600;
                font-size: 14px;
                padding: 12px 24px;
                border-radius: 6px;
                box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2);
                transition: background-color 0.2s;
            }}
            .btn:hover {{
                background-color: #1d4ed8;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="banner">
                <div class="icon-wrapper">⚠️</div>
                <h1>Phishing Simulation Interception</h1>
                <p>Oops! You clicked on a simulated phishing link.</p>
            </div>
            <div class="content">
                <p class="intro-text">
                    Hello <strong>{employee.first_name} {employee.last_name}</strong>. This was a safe, educational security simulation conducted by Phintra. Don't worry—your credentials were not stolen and your device is completely safe. However, in a real attack, clicking this link could have compromised the company network.
                </p>
                <div class="details-box">
                    <div class="details-title">Simulation Details</div>
                    <div class="details-row">
                        <span class="details-label">Subject:</span>
                        <span class="details-val">{template_subject}</span>
                    </div>
                    <div class="details-row">
                        <span class="details-label">Sender:</span>
                        <span class="details-val">{template_sender}</span>
                    </div>
                </div>
                <h2>Critical Indicators You Missed</h2>
                <ul>
                    <li><strong>Display Name Spoofing:</strong> Attackers often use trusted names but send from unverified external domains.</li>
                    <li><strong>Lookalike Hyperlinks:</strong> Always hover over links before clicking. Look for spelling variations in domain names (e.g. g00gle.com instead of google.com).</li>
                    <li><strong>Urgency Cues:</strong> High pressure language demanding immediate action is a common social engineering tactic to bypass critical thinking.</li>
                </ul>
                <a id="portal-link" href="http://localhost:5174/user/training" class="btn">Return to Security Dashboard & Training</a>
            </div>
        </div>
        <script>
            const ports = [5173, 5174];
            const link = document.getElementById("portal-link");
            function tryPort(index) {{
                if (index >= ports.length) return;
                const port = ports[index];
                const url = "http://localhost:" + port + "/";
                fetch(url, {{ mode: 'no-cors' }}).then(() => {{
                    link.href = "http://localhost:" + port + "/user/training";
                }}).catch(() => {{
                    tryPort(index + 1);
                }});
            }}
            tryPort(0);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)

@router.post("/campaigns/click/{track_id}", status_code=status.HTTP_201_CREATED)
def record_campaign_click(track_id: UUID, click_in: CampaignClickCreate, db: Session = Depends(get_db)):
    """Record click event for campaign recipient tracking (Public Endpoint)."""
    from datetime import datetime
    from app.utils.scoring import log_activity_event
    # 1. Fetch CampaignRecipient
    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.track_id == track_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Invalid or expired tracking identifier")
        
    # 2. Get Campaign and Employee details
    campaign = db.query(Campaign).filter(Campaign.id == recipient.campaign_id).first()
    employee = db.query(Employee).filter(Employee.id == recipient.employee_id).first()
    if not campaign or not employee:
        raise HTTPException(status_code=404, detail="Associated campaign or employee records not found")
        
    # 3. Insert CampaignClick
    already_clicked = db.query(CampaignClick).filter(
        CampaignClick.campaign_id == campaign.id,
        CampaignClick.employee_id == employee.id,
        CampaignClick.track_id == track_id
    ).first()
    
    if not already_clicked:
        click = CampaignClick(
            admin_id=employee.admin_id if employee.admin_id else campaign.created_by,
            campaign_id=campaign.id,
            employee_id=employee.id,
            email=employee.email,
            track_id=track_id,
            ip_address=click_in.ip_address,
            user_agent=click_in.user_agent,
            status="Clicked"
        )
        db.add(click)
        
        # 4. Update CampaignRecipient status and timestamp
        recipient.status = "Clicked"
        recipient.clicked_at = datetime.utcnow()
        
        # 5. Update EmailLog status if exists
        from app.models.email_log import EmailLog
        db.query(EmailLog).filter(
            EmailLog.campaign_id == campaign.id,
            EmailLog.employee_id == employee.id
        ).update({"status": "Clicked"}, synchronize_session=False)
        
        # Use log_activity_event for behavioral score updates
        log_activity_event(db, employee.id, "link_clicked", campaign_id=campaign.id)
        
        db.commit()
        
    return {"message": "Click registered successfully"}


@router.get("/campaigns/alerts", response_model=List[CampaignAlertResponse])
def get_campaign_alerts(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Get recent campaign clicks for dashboard notification alert cards (Managers & Admins)."""
    clicks = db.query(CampaignClick).filter(CampaignClick.admin_id == current_user.id).order_by(CampaignClick.clicked_at.desc()).limit(15).all()
    results = []
    for c in clicks:
        emp = db.query(Employee).filter(Employee.id == c.employee_id).first()
        camp = db.query(Campaign).filter(Campaign.id == c.campaign_id).first()
        if emp and camp:
            results.append(CampaignAlertResponse(
                employee_name=f"{emp.first_name} {emp.last_name}",
                employee_email=emp.email,
                campaign_name=camp.name,
                clicked_at=c.clicked_at,
                risk_status=emp.status
            ))
    return results


@router.get("/campaigns/analytics/{campaign_id}", response_model=CampaignAnalyticsResponse)
@router.get("/campaigns/{campaign_id}/analytics", response_model=CampaignAnalyticsResponse)
def get_campaign_analytics(campaign_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Retrieve campaign click rates and analytics (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)
    # 1. Verify campaign belongs to admin
    camp = db.query(Campaign).filter(Campaign.id == campaign_id, (Campaign.admin_id == admin_id) | (Campaign.admin_id == None)).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    # 2. Get recipients
    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id).all()
    
    # 3. Filter employees to only those belonging to this admin
    valid_recipients = []
    # Fetch sender profile if assigned
    sender_profile = None
    if camp.sender_profile_id:
        from app.models.sender_profile import SenderProfile
        sender_profile = db.query(SenderProfile).filter(SenderProfile.profile_id == camp.sender_profile_id).first()

    for r in recipients:
        emp = db.query(Employee).filter(
            Employee.id == r.employee_id,
            (Employee.company_id == company_id) | (Employee.admin_id == admin_id)
        ).first()
        if emp:
            valid_recipients.append((r, emp))
            
    total_sent = len(valid_recipients)
    
    # Calculate status aggregates from email logs
    from app.models.email_log import EmailLog
    failed_count = db.query(EmailLog).filter(
        EmailLog.campaign_id == campaign_id,
        EmailLog.status == "Failed"
    ).count()
    
    # For clicks, check CampaignClicks table
    clicks = db.query(CampaignClick).filter(
        CampaignClick.campaign_id == campaign_id,
        CampaignClick.admin_id == current_user.id
    ).all()
    total_clicked = len(clicks)
    
    # Gather employee details
    clicked_emp_ids = {c.employee_id for c in clicks}
    
    clicked_employees = []
    non_clicked_employees = []
    
    for r, emp in valid_recipients:
        dept = db.query(Department).filter(Department.id == emp.department_id).first()
        dept_name = dept.name if dept else "Unknown"
        
        if emp.id in clicked_emp_ids:
            # Find click details
            c_detail = next((c for c in clicks if c.employee_id == emp.id), None)
            clicked_employees.append(ClickedEmployeeInfo(
                name=f"{emp.first_name} {emp.last_name}",
                email=emp.email,
                department=dept_name,
                clicked_at=c_detail.clicked_at if c_detail else r.updated_at,
                ip_address=c_detail.ip_address if c_detail else "Unknown",
                user_agent=c_detail.user_agent if c_detail else "Unknown"
            ))
        else:
            non_clicked_employees.append(NonClickedEmployeeInfo(
                name=f"{emp.first_name} {emp.last_name}",
                email=emp.email,
                department=dept_name,
                status=r.status
            ))
            
    # Department click counts
    dept_clicks = {}
    dept_totals = {}
    for r, emp in valid_recipients:
        dept = db.query(Department).filter(Department.id == emp.department_id).first()
        dept_name = dept.name if dept else "Unknown"
        dept_totals[dept_name] = dept_totals.get(dept_name, 0) + 1
        if emp.id in clicked_emp_ids:
            dept_clicks[dept_name] = dept_clicks.get(dept_name, 0) + 1
            
    department_risk = []
    for d_name in dept_totals:
        department_risk.append(DepartmentRiskInfo(
            department_name=d_name,
            click_count=dept_clicks.get(d_name, 0),
            total_employees=dept_totals[d_name]
        ))
        
    from app.models.reported_email import ReportedEmail
    reported_emails_q = db.query(ReportedEmail).filter(ReportedEmail.campaign_id == campaign_id).all()
    
    reported_employees = []
    for r in reported_emails_q:
        emp = db.query(Employee).filter(
            Employee.id == r.employee_id,
            (Employee.company_id == company_id) | (Employee.admin_id == admin_id)
        ).first()
        if emp:
            dept = db.query(Department).filter(Department.id == r.department_id).first() if r.department_id else None
            dept_name = dept.name if dept else "Unknown"
            reported_employees.append(ReportedEmployeeInfo(
                name=r.employee_name or f"{emp.first_name} {emp.last_name}",
                email=r.employee_email or emp.email,
                department=dept_name,
                reported_at=r.created_at or r.reported_at
            ))
            
    total_reported = len(reported_employees)
    click_rate = (total_clicked / total_sent * 100.0) if total_sent > 0 else 0.0
    reported_rate = (total_reported / total_sent * 100.0) if total_sent > 0 else 0.0

    # Calculate opens and training completions
    total_opened = sum(1 for r, emp in valid_recipients if r.opened_at is not None or r.status in ["Opened", "Clicked", "Reported"])
    open_rate = (total_opened / total_sent * 100.0) if total_sent > 0 else 0.0
    
    training_completed_count = sum(1 for r, emp in valid_recipients if r.training_completed_at is not None or r.status == "Completed Training")
    training_completion_rate = (training_completed_count / total_sent * 100.0) if total_sent > 0 else 0.0
    
    return CampaignAnalyticsResponse(
        total_sent=total_sent,
        total_delivered=max(0, total_sent - failed_count),
        total_failed=failed_count,
        total_clicked=total_clicked,
        total_reported=total_reported,
        click_rate_percentage=round(click_rate, 2),
        reported_rate_percentage=round(reported_rate, 2),
        clicked_employees=clicked_employees,
        reported_employees=reported_employees,
        non_clicked_employees=non_clicked_employees,
        department_risk=department_risk,
        total_opened=total_opened,
        open_rate_percentage=round(open_rate, 2),
        training_completed_count=training_completed_count,
        training_completion_rate_percentage=round(training_completion_rate, 2)
    )


from pydantic import BaseModel
class ReportSubmitRequest(BaseModel):
    employee_id: UUID
    campaign_id: UUID
    action: str

@router.get("/campaigns/track/{track_id}")
def get_campaign_track_info(track_id: UUID, request: Request, db: Session = Depends(get_db)):
    """Retrieve info about a campaign click tracking code and log the click action (Public)."""
    from datetime import datetime
    from app.utils.scoring import log_activity_event
    recipient = db.query(CampaignRecipient).filter(CampaignRecipient.track_id == track_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Invalid tracking code")
        
    campaign = db.query(Campaign).filter(Campaign.id == recipient.campaign_id).first()
    employee = db.query(Employee).filter(Employee.id == recipient.employee_id).first()
    if not campaign or not employee:
        raise HTTPException(status_code=404, detail="Associated records not found")
        
    # Log the Click event if not already done
    if recipient.status not in ["Clicked", "Reported"]:
        recipient.status = "Clicked"
        recipient.clicked_at = datetime.utcnow()
        
        user_agent = request.headers.get("User-Agent", "Unknown")
        ip_address = request.client.host if request.client else "127.0.0.1"
        
        already_clicked = db.query(CampaignClick).filter(
            CampaignClick.campaign_id == campaign.id,
            CampaignClick.employee_id == employee.id,
            CampaignClick.track_id == track_id
        ).first()
        
        if not already_clicked:
            click = CampaignClick(
                admin_id=employee.admin_id if employee.admin_id else campaign.created_by,
                campaign_id=campaign.id,
                employee_id=employee.id,
                email=employee.email,
                track_id=track_id,
                ip_address=ip_address,
                user_agent=user_agent,
                status="Clicked"
            )
            db.add(click)
            
            from app.models.email_log import EmailLog
            db.query(EmailLog).filter(
                EmailLog.campaign_id == campaign.id,
                EmailLog.employee_id == employee.id
            ).update({"status": "Clicked"}, synchronize_session=False)
            
            # Use log_activity_event for behavioral score updates
            log_activity_event(db, employee.id, "link_clicked", campaign_id=campaign.id)
            
        db.commit()
        
    # Get template body
    email_body = "This is a simulated phishing email."
    email_subject = "Security Alert"
    awareness_page_data = None
    
    if campaign.template_id:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == campaign.template_id).first()
        if template:
            email_subject = template.subject
            import json
            try:
                data = json.loads(template.body_html)
                email_body = data.get("body", template.body_html)
            except Exception:
                email_body = template.body_html
                
        # Resolve custom linked awareness page config
        pages = db.query(AwarenessPage).all()
        for page in pages:
            try:
                import json
                config = json.loads(page.html_content)
                if config.get("email_template_id") == str(campaign.template_id):
                    awareness_page_data = {
                        "title": page.title,
                        "message": config.get("message"),
                        "tips": config.get("tips", []),
                        "cta_text": config.get("ctaText"),
                        "theme": config.get("theme")
                    }
                    break
            except Exception:
                pass
                
    return {
        "employee_id": str(recipient.employee_id),
        "campaign_id": str(recipient.campaign_id),
        "employee_name": f"{employee.first_name} {employee.last_name}",
        "campaign_name": campaign.name,
        "email_subject": email_subject,
        "email_body": email_body,
        "status": recipient.status,
        "awareness_page": awareness_page_data
    }

@router.post("/report", status_code=status.HTTP_201_CREATED)
def create_report_log(req: ReportSubmitRequest, db: Session = Depends(get_db)):
    """Log an employee's action on a simulated email (Public)."""
    from datetime import datetime
    from app.utils.scoring import log_activity_event
    if req.action not in ["report", "safe"]:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'report' or 'safe'")
        
    recipient = db.query(CampaignRecipient).filter(
        CampaignRecipient.campaign_id == req.campaign_id,
        CampaignRecipient.employee_id == req.employee_id
    ).first()
    
    if recipient:
        if req.action == "report":
            recipient.status = "Reported"
            recipient.reported_at = datetime.utcnow()
            
            # Log event
            log_activity_event(db, req.employee_id, "email_reported", campaign_id=req.campaign_id)
        db.commit()
        
    from app.models.campaign import ReportLog
    report_log = ReportLog(
        employee_id=req.employee_id,
        campaign_id=req.campaign_id,
        action=req.action
    )
    db.add(report_log)
    db.commit()
    db.refresh(report_log)
    
    from app.models.reported_email import ReportedEmail
    from app.models.notification import Notification
    
    emp = db.query(Employee).filter(Employee.id == req.employee_id).first()
    camp = db.query(Campaign).filter(Campaign.id == req.campaign_id).first()
    
    # Get template body/subject
    email_subject = "Simulated Phishing Link Clicked"
    email_body = "This was a simulated phishing email."
    email_sender = "lure@phintra-sim.com"
    if camp and camp.template_id:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == camp.template_id).first()
        if template:
            email_subject = template.subject
            import json
            try:
                data = json.loads(template.body_html)
                email_body = data.get("body", template.body_html)
            except Exception:
                email_body = template.body_html
                
    # Check if already in ReportedEmail
    already_reported = db.query(ReportedEmail).filter(
        ReportedEmail.employee_id == req.employee_id,
        ReportedEmail.campaign_id == req.campaign_id
    ).first()
    
    if not already_reported:
        db_report = ReportedEmail(
            employee_id=req.employee_id,
            employee_name=f"{emp.first_name} {emp.last_name}" if emp else "Unknown Employee",
            employee_email=emp.email if emp else "unknown@company.com",
            campaign_id=req.campaign_id,
            campaign_name=camp.name if camp else "Simulated Campaign",
            email_subject=email_subject,
            email_sender=email_sender,
            email_body=email_body,
            report_reason="Employee flagged the simulation email." if req.action == "report" else "Employee marked the email as safe.",
            report_status="Suspicious" if req.action == "report" else "Safe",
            department_id=emp.department_id if emp else None,
            risk_score=50 if req.action == "report" else 10,
            risk_level="Medium" if req.action == "report" else "Low"
        )
        db.add(db_report)
        db.commit()
        
        # Send Notification to Admin
        title = "Simulated phishing email reported" if req.action == "report" else "Email marked safe"
        msg = f"{emp.first_name} {emp.last_name} successfully reported a simulated phishing email." if req.action == "report" else f"{emp.first_name} {emp.last_name} marked a simulated email as safe."
        
        notif = Notification(
            user_id=None,
            employee_id=req.employee_id,
            title=title,
            message=msg,
            is_read=False
        )
        db.add(notif)
        db.commit()
        
        if req.action == "report" and emp:
            emp.risk_score = max(0.0, emp.risk_score - 10.0)
            if emp.risk_score < 20.0:
                emp.status = "Low Risk"
            elif emp.risk_score < 50.0:
                emp.status = "Medium Risk"
            elif emp.risk_score < 80.0:
                emp.status = "High Risk"
            else:
                emp.status = "Critical Risk"
                
            from app.models.certificate import Reward
            reward = Reward(
                employee_id=emp.id,
                xp_amount=100,
                description=f"Successfully reported phishing simulation: {camp.name if camp else 'Simulation'}"
            )
            db.add(reward)
            db.commit()
            
    return {"status": "success", "message": f"Action '{req.action}' recorded successfully."}


@router.get("/campaigns/employee/campaign-feed")
@router.get("/employee/campaign-feed")
def get_employee_campaign_feed(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all phishing simulation campaigns dispatched to the logged-in employee."""
    emp = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not emp:
        emp = db.query(Employee).filter(Employee.email == current_user.email).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee profile not found")
            
    # Fetch all recipient records for this employee
    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.employee_id == emp.id).all()
    
    feed = []
    for cr in recipients:
        camp = db.query(Campaign).filter(Campaign.id == cr.campaign_id).first()
        if not camp:
            continue
            
        template = db.query(EmailTemplate).filter(EmailTemplate.id == camp.template_id).first()
        
        # Determine subject, sender, and description
        subject = template.subject if template else "Simulated Phishing Drill"
        sender_name = template.sender_name if (template and template.sender_name) else "IT Security Alert"
        description = template.title if template else "Corporate Phishing Simulation"
        difficulty = template.difficulty if template else "Medium"
        category = template.category if template else "Suspicious Link"
        
        feed.append({
            "campaign_id": str(camp.id),
            "campaign_name": camp.name,
            "send_date": (cr.created_at or camp.launch_date or camp.created_at).isoformat(),
            "type": camp.type,
            "subject": subject,
            "sender_name": sender_name,
            "description": description,
            "difficulty": difficulty,
            "category": category,
            "interaction_status": cr.status, # Sent, Opened, Clicked, Reported
            "track_id": str(cr.track_id)
        })
        
    # Sort feed by send_date descending
    feed.sort(key=lambda x: x["send_date"], reverse=True)
    return feed


@router.post("/campaigns/employee/report-campaign/{campaign_id}")
@router.post("/employee/report-campaign/{campaign_id}")
def report_campaign_simulation(
    campaign_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Report a phishing campaign email directly from the employee feed/inbox."""
    emp = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not emp:
        emp = db.query(Employee).filter(Employee.email == current_user.email).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee profile not found")

    recipient = db.query(CampaignRecipient).filter(
        CampaignRecipient.campaign_id == campaign_id,
        CampaignRecipient.employee_id == emp.id
    ).first()
    
    if not recipient:
        raise HTTPException(status_code=404, detail="Campaign record not found for employee")
        
    if recipient.status == "Reported":
        return {"status": "success", "message": "Email has already been reported."}
        
    # Update interaction status
    recipient.status = "Reported"
    
    camp = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    template = db.query(EmailTemplate).filter(EmailTemplate.id == camp.template_id).first() if camp else None
    
    email_subject = template.subject if template else (camp.name if camp else "Phishing Simulation")
    email_sender = template.sender_name if (template and template.sender_name) else "simulation@phintra.com"
    email_body = template.body_html if template else "This was a simulated phishing email."
    
    # Store in ReportedEmail table
    from app.models.reported_email import ReportedEmail
    
    # Check if already in ReportedEmail
    already_reported = db.query(ReportedEmail).filter(
        ReportedEmail.employee_id == emp.id,
        ReportedEmail.campaign_id == campaign_id
    ).first()
    
    if not already_reported:
        db_report = ReportedEmail(
            employee_id=emp.id,
            employee_name=f"{emp.first_name} {emp.last_name}".strip() or "Employee",
            employee_email=emp.email,
            campaign_id=campaign_id,
            campaign_name=camp.name if camp else "Simulated Campaign",
            email_subject=email_subject,
            email_sender=email_sender,
            email_body=email_body,
            report_reason="Employee flagged the simulation email from inbox feed.",
            report_status="reported", # Lifecycle: reported, reviewed, resolved
            department_id=emp.department_id,
            risk_score=50,
            risk_level="Medium",
            admin_id=emp.admin_id
        )
        db.add(db_report)
        
        # Update Risk Score
        emp.risk_score = max(0.0, emp.risk_score - 10.0)
        if emp.risk_score < 20.0:
            emp.status = "Low Risk"
        elif emp.risk_score < 50.0:
            emp.status = "Medium Risk"
        elif emp.risk_score < 80.0:
            emp.status = "High Risk"
        else:
            emp.status = "Critical Risk"
            
        # Award 100 XP
        from app.models.certificate import Reward
        reward = Reward(
            employee_id=emp.id,
            xp_amount=100,
            description=f"Successfully reported phishing simulation: {camp.name if camp else 'Simulation'}"
        )
        db.add(reward)
        
        # Notify Admin
        from app.models.notification import Notification
        notif = Notification(
            user_id=None,
            employee_id=emp.id,
            title="Simulated phishing email reported",
            message=f"{emp.first_name} {emp.last_name} successfully reported a simulated phishing email.",
            is_read=False
        )
        db.add(notif)
        
        # Audit Log
        from app.models.audit_log import AuditLog
        audit = AuditLog(
            action="Report Campaign Simulation",
            details=f"Employee {emp.email} reported campaign simulation {camp.name if camp else campaign_id}."
        )
        db.add(audit)
        
        db.commit()
        
    return {"status": "success", "message": "Email simulation successfully reported."}

