from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
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
from app.utils.dependencies import require_manager
from app.models.audit_log import AuditLog
from uuid import UUID
from typing import List

router = APIRouter(tags=["Campaigns"])

# =====================================================================
# CAMPAIGN ENDPOINTS
# =====================================================================

from app.models.department import Department

@router.get("/campaigns", response_model=List[CampaignResponse])
def list_campaigns(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """List all simulation campaigns with stats aggregates (Managers & Admins)."""
    campaigns = db.query(Campaign).filter(Campaign.created_by == current_user.id).all()
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
    c = db.query(Campaign).filter(Campaign.id == id, Campaign.created_by == current_user.id).first()
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
    name_val = camp_in.title if camp_in.title else camp_in.name
    type_val = camp_in.campaign_type if camp_in.campaign_type else camp_in.type
    
    if not name_val:
        raise HTTPException(status_code=400, detail="Campaign name or title is required")
        
    db_camp = Campaign(
        name=name_val,
        type=type_val if type_val else "Link Phishing",
        status=camp_in.status if camp_in.status else "Draft",
        launch_date=camp_in.launch_date,
        department_id=camp_in.department_id,
        template_id=camp_in.template_id,
        created_by=current_user.id
    )
    db.add(db_camp)
    db.commit()
    db.refresh(db_camp)
    
    # Assign employees if provided
    if camp_in.employee_ids:
        for emp_id in camp_in.employee_ids:
            emp = db.query(Employee).filter(Employee.id == emp_id, Employee.admin_id == current_user.id).first()
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
    camp = db.query(Campaign).filter(Campaign.id == id, Campaign.created_by == current_user.id).first()
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

@router.post("/campaigns/{id}/send-test")
def send_campaign_test_email(id: UUID, req: dict, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Send a single test email of the campaign to the admin/manager email."""
    camp = db.query(Campaign).filter(Campaign.id == id, Campaign.created_by == current_user.id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    test_email = req.get("test_email")
    if not test_email:
        raise HTTPException(status_code=400, detail="test_email is required")
        
    # Retrieve template
    if not camp.template_id:
        template = db.query(EmailTemplate).first()
    else:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == camp.template_id).first()
        
    if not template:
        raise HTTPException(status_code=400, detail="No email template is configured for this campaign")
        
    # Reconstruct body & subject
    import json
    try:
        template_data = json.loads(template.body_html)
        subject = template.subject
        body = template_data.get("body", template.body_html)
    except Exception:
        subject = template.subject
        body = template.body_html
        
    import uuid
    tracking_link = f"http://127.0.0.1:8001/campaigns/click/{uuid.uuid4()}"
    personalized_body = body.replace("{{login_link}}", tracking_link)
    personalized_body = personalized_body.replace("{{employee_name}}", "Test Recipient")
    personalized_body = personalized_body.replace("{{company_name}}", "Phintra Test Lab")
    
    success = send_email(db, test_email, f"[TEST] {subject}", personalized_body)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send test SMTP email. Check SMTP settings in .env.")
        
    return {"status": "success", "message": f"Test email sent to {test_email}"}

@router.post("/campaigns/{id}/launch")
def launch_campaign_route(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Launch/deploy the campaign: set active, send emails to all recipients (Managers & Admins)."""
    from datetime import datetime
    camp = db.query(Campaign).filter(Campaign.id == id, Campaign.created_by == current_user.id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    camp.status = "Active"
    camp.launch_date = datetime.utcnow()
    
    # Retrieve template
    if not camp.template_id:
        template = db.query(EmailTemplate).first()
    else:
        template = db.query(EmailTemplate).filter(EmailTemplate.id == camp.template_id).first()
        
    if not template:
        raise HTTPException(status_code=400, detail="No email template is configured for this campaign")
        
    # Get all recipients
    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == id).all()
    
    sent_count = 0
    failed_count = 0
    
    for r in recipients:
        emp = db.query(Employee).filter(Employee.id == r.employee_id, Employee.admin_id == current_user.id).first()
        if not emp:
            continue
            
        # Ensure track_id is set
        if not r.track_id:
            import uuid
            r.track_id = uuid.uuid4()
            
        # Personalize tracking link
        tracking_link = f"http://127.0.0.1:8001/campaigns/click/{r.track_id}"
        
        import json
        try:
            template_data = json.loads(template.body_html)
            subject = template.subject
            body = template_data.get("body", template.body_html)
        except Exception:
            subject = template.subject
            body = template.body_html
            
        # Personalize placeholders
        personalized_body = body.replace("{{login_link}}", tracking_link)
        personalized_body = personalized_body.replace("{{employee_name}}", f"{emp.first_name} {emp.last_name}")
        personalized_body = personalized_body.replace("{{company_name}}", "Phintra Enterprise")
        
        success = send_email(
            db,
            emp.email,
            subject,
            personalized_body,
            campaign_id=camp.id,
            template_id=template.id,
            employee_id=emp.id
        )
        if success:
            r.status = "Sent"
            sent_count += 1
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
    camp = db.query(Campaign).filter(Campaign.id == id, Campaign.created_by == current_user.id).first()
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
    camp = db.query(Campaign).filter(Campaign.id == id, Campaign.created_by == current_user.id).first()
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
    camp = db.query(Campaign).filter(Campaign.id == id, Campaign.created_by == current_user.id).first()
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
    for r in recipients:
        emp = db.query(Employee).filter(Employee.id == r.employee_id, Employee.admin_id == current_user.id).first()
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
    # Verify campaign belongs to admin
    camp = db.query(Campaign).filter(Campaign.id == id, Campaign.created_by == current_user.id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == id).all()
    results = []
    for r in recipients:
        emp = db.query(Employee).filter(Employee.id == r.employee_id, Employee.admin_id == current_user.id).first()
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
    camp = db.query(Campaign).filter(Campaign.id == id, Campaign.created_by == current_user.id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    results = []
    for emp_id in req.employee_ids:
        # Verify employee exists and belongs to this admin
        emp = db.query(Employee).filter(Employee.id == emp_id, Employee.admin_id == current_user.id).first()
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
    camp = db.query(Campaign).filter(Campaign.id == id, Campaign.created_by == current_user.id).first()
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
        emp = db.query(Employee).filter(Employee.id == recipient.employee_id, Employee.admin_id == current_user.id).first()
        if not emp:
            continue
            
        success = send_email(db, emp.email, subject, body)
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

@router.get("/email-templates", response_model=List[EmailTemplateResponse])
def list_email_templates(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """List simulation email templates (Managers & Admins)."""
    return db.query(EmailTemplate).all()

@router.post("/email-templates", response_model=EmailTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_email_template(temp_in: EmailTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Create simulation email template (Managers & Admins)."""
    db_temp = EmailTemplate(**temp_in.dict())
    db.add(db_temp)
    db.commit()
    db.refresh(db_temp)
    return db_temp

@router.put("/email-templates/{id}", response_model=EmailTemplateResponse)
def update_email_template(id: UUID, temp_in: EmailTemplateUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Update simulation email template (Managers & Admins)."""
    temp = db.query(EmailTemplate).filter(EmailTemplate.id == id).first()
    if not temp:
        raise HTTPException(status_code=404, detail="Template not found")
        
    update_data = temp_in.dict(exclude_unset=True)
    for key, val in update_data.items():
        setattr(temp, key, val)
        
    db.commit()
    db.refresh(temp)
    return temp

@router.delete("/email-templates/{id}", status_code=status.HTTP_200_OK)
def delete_email_template(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Delete simulation email template (Managers & Admins)."""
    temp = db.query(EmailTemplate).filter(EmailTemplate.id == id).first()
    if not temp:
        raise HTTPException(status_code=404, detail="Template not found")
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

@router.get("/campaigns/click/{track_id}", response_class=HTMLResponse)
def record_campaign_click_get(track_id: UUID, request: Request, db: Session = Depends(get_db)):
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
        
        # 4. Update CampaignRecipient status
        recipient.status = "Clicked"
        
        # 5. Update EmailLog status if exists
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
def get_campaign_analytics(campaign_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Retrieve campaign click rates and analytics (Managers & Admins)."""
    # 1. Verify campaign belongs to admin
    camp = db.query(Campaign).filter(Campaign.id == campaign_id, Campaign.created_by == current_user.id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    # 2. Get recipients
    recipients = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id).all()
    
    # 3. Filter employees to only those belonging to this admin
    valid_recipients = []
    for r in recipients:
        emp = db.query(Employee).filter(Employee.id == r.employee_id, Employee.admin_id == current_user.id).first()
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
        
    from app.models.certificate import ReportedEmail
    reported_emails_q = db.query(ReportedEmail).filter(ReportedEmail.campaign_id == campaign_id).all()
    
    reported_employees = []
    for r in reported_emails_q:
        emp = db.query(Employee).filter(Employee.id == r.employee_id, Employee.admin_id == current_user.id).first()
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
        department_risk=department_risk
    )
