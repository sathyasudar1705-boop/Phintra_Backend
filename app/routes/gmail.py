from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import secrets
import traceback
import os
from typing import List, Optional

from app.database import get_db
from app.models.employee import Employee
from app.models.company import Company
from app.models.reported_email import ReportedEmail
from app.models.certificate import Reward
from app.models.user import User
from app.models.notification import Notification
from app.models.audit_log import SecurityScore
from app.models.campaign import Campaign, CampaignRecipient
from app.models.email_log import EmailLog
from app.models.message import Message

from app.schemas.reported_email_schema import GmailReportEmailCreate, GmailAdminMessageCreate
from app.services.ai_service import analyze_email_risk

router = APIRouter(tags=["Gmail Add-on"])

@router.post("/gmail/report-email", status_code=status.HTTP_200_OK)
def report_email_from_gmail(req: GmailReportEmailCreate, request: Request, db: Session = Depends(get_db)):
    """Ingest a suspicious email report from Gmail Add-on, analyze risk with local AI, store, and return side panel results."""
    try:
        # 1. SECURITY VALIDATION: Validate X-PHINTRA-ADDON-KEY if set in env
        addon_key = os.getenv("PHINTRA_ADDON_KEY", "phintra-dev-key-123")
        req_key = request.headers.get("X-PHINTRA-ADDON-KEY")
        is_addon_authenticated = (req_key == addon_key)

        # Authenticate JWT token if present
        authenticated_user = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                from app.dependencies import get_current_user
                authenticated_user = get_current_user(token=token, db=db)
            except Exception:
                pass

        if not is_addon_authenticated and not authenticated_user:
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Employee email not registered under this company."}
            )

        # 2. EXTRACT AND VALIDATE EMPLOYEE_EMAIL
        reporter_email = req.employee_email or req.reported_user_email
        if not reporter_email:
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Employee email not registered under this company."}
            )
        normalized_email = reporter_email.strip().lower()

        # 3. CONFIRM EMPLOYEE EXISTS IN DB
        emp = db.query(Employee).filter(func.lower(Employee.email) == normalized_email).first()
        if not emp:
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": "Employee email not registered under this company."}
            )

        # 4. VERIFY SCOPE IF JWT AUTHENTICATED
        if authenticated_user:
            reported_company_id = emp.company_id
            reported_admin_id = emp.admin_id
            
            auth_company_id = None
            auth_admin_id = None

            if authenticated_user.role in ["Employee", "employee"]:
                auth_emp = db.query(Employee).filter(Employee.id == authenticated_user.id).first()
                if auth_emp:
                    auth_company_id = auth_emp.company_id
                    auth_admin_id = auth_emp.admin_id
            else:
                admin_id = authenticated_user.id
                if authenticated_user.role not in ["Admin", "admin"] and hasattr(authenticated_user, "admin_id") and authenticated_user.admin_id:
                    admin_id = authenticated_user.admin_id
                auth_admin_id = admin_id
                auth_company = db.query(Company).filter(Company.admin_id == admin_id).first()
                if auth_company:
                    auth_company_id = auth_company.id

            scopes_match = False
            if auth_company_id and reported_company_id:
                if auth_company_id == reported_company_id:
                    scopes_match = True
            else:
                if auth_admin_id and auth_admin_id == reported_admin_id:
                    scopes_match = True

            if not scopes_match:
                return JSONResponse(
                    status_code=403,
                    content={"success": False, "error": "Employee email not registered under this company."}
                )

        # 5. PROCESS THE VALID REPORT
        email_subject = req.subject if req.subject else (req.email_subject or "No subject")
        email_sender = req.sender if req.sender else (req.email_sender or "Unknown sender")
        email_body = req.body if req.body else (req.email_body or "")
        message_id = req.message_id
        thread_id = req.thread_id
        
        reported_at_val = datetime.now()
        reported_time_str = req.reported_at or req.reported_time
        if reported_time_str:
            try:
                reported_at_val = datetime.fromisoformat(reported_time_str.replace("Z", "+00:00"))
            except Exception:
                try:
                    reported_at_val = datetime.strptime(reported_time_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

        # Run AI threat analysis
        analysis = analyze_email_risk(email_subject, email_sender, email_body)
        
        employee_id = emp.id
        employee_name = f"{emp.first_name} {emp.last_name}" if emp.first_name else (emp.name or "Portal Test Employee")
        employee_email = emp.email
        department_id = emp.department_id

        # CAMPAIGN AUTO MAPPING
        campaign_id = None
        campaign_name = "External Gmail Report"
        is_campaign = False

        if employee_email and email_subject:
            email_log = db.query(EmailLog).filter(
                EmailLog.recipient_email == employee_email.strip(),
                EmailLog.subject == email_subject.strip()
            ).order_by(EmailLog.sent_at.desc()).first()
            
            if email_log:
                campaign_id = email_log.campaign_id
                campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
                if campaign:
                    campaign_name = campaign.name
                is_campaign = True
                
                # Update CampaignRecipient status
                recipient = db.query(CampaignRecipient).filter(
                    CampaignRecipient.campaign_id == campaign_id,
                    CampaignRecipient.employee_id == employee_id
                ).first()
                if recipient:
                    recipient.status = "Reported"
                email_log.status = "Reported"

        # Points (XP) awarding
        points_added = 150 if is_campaign else 10
        reward_desc = f"Successfully Spotted Simulated Phishing: {email_subject}" if is_campaign else f"Phishing Threat Reported: {email_subject}"
        
        existing_reward = db.query(Reward).filter(
            Reward.employee_id == employee_id,
            Reward.description == reward_desc
        ).first()
        
        if not existing_reward:
            reward = Reward(
                employee_id=employee_id,
                xp_amount=points_added,
                description=reward_desc
            )
            db.add(reward)

        # Update employee risk score
        reduction = 15.0 if is_campaign else 2.0
        emp.risk_score = max(0.0, emp.risk_score - reduction)
        if emp.risk_score < 20.0:
            emp.status = "Low Risk"
        elif emp.risk_score < 50.0:
            emp.status = "Medium Risk"
        elif emp.risk_score < 80.0:
            emp.status = "High Risk"
        else:
            emp.status = "Critical"

        score_entry = SecurityScore(employee_id=employee_id, score=(100.0 - emp.risk_score))
        db.add(score_entry)

        # Create ReportedEmail record
        db_report = ReportedEmail(
            employee_id=employee_id,
            employee_name=employee_name,
            employee_email=employee_email,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            reported_by=None,
            department_id=department_id,
            report_source="gmail_addon",
            message_id=message_id,
            thread_id=thread_id,
            email_subject=email_subject,
            email_sender=email_sender,
            sender_email=email_sender,
            email_body=email_body,
            threat_score=analysis["risk_score"],
            risk_score=analysis["risk_score"],
            risk_level=analysis["risk_level"],
            status="Pending",
            report_status="Pending",
            report_reason="Reported from Gmail Add-on",
            subject=email_subject,
            sender=email_sender,
            email_date=req.email_date or reported_at_val,
            reported_at=reported_at_val,
            created_at=reported_at_val,
            analysis_results=analysis
        )
        db.add(db_report)
        db.commit()
        db.refresh(db_report)

        # Create Admin Notifications — scoped to employee's own company admin only
        target_admin_id = emp.admin_id
        if not target_admin_id and emp.company_id:
            company_row = db.query(Company).filter(Company.id == emp.company_id).first()
            if company_row:
                target_admin_id = company_row.admin_id
        if target_admin_id:
            scoped_admins = db.query(User).filter(User.id == target_admin_id).all()
        else:
            scoped_admins = db.query(User).filter(User.role == "Admin").all()

        for admin in scoped_admins:
            sec_notif = Notification(
                user_id=admin.id,
                employee_id=employee_id,
                title="New Email Reported",
                message=f"Employee {employee_name} reported a suspicious email.",
                notification_type="security_alert",
                is_read=False
            )
            db.add(sec_notif)

        if analysis["risk_level"] == "Critical":
            for admin in scoped_admins:
                admin_notif = Notification(
                    user_id=admin.id,
                    employee_id=employee_id,
                    title="Critical Phishing Threat Reported",
                    message=f"Critical threat reported by {email_sender}: '{email_subject}' (Score: {analysis['risk_score']})",
                    notification_type="security_alert",
                    is_read=False
                )
                db.add(admin_notif)

        db.commit()

        # Calculate employee current score (total XP)
        employee_score = db.query(func.sum(Reward.xp_amount)).filter(Reward.employee_id == employee_id).scalar() or 0

        # Calculate leaderboard rank
        leaderboard_rank = 1
        company_id = emp.company_id
        if company_id:
            from app.models.training import TrainingCompletion, TrainingModule
            admin_id = db.query(Company.admin_id).filter(Company.id == company_id).scalar()
            total_modules = db.query(TrainingModule).filter(TrainingModule.admin_id == admin_id).count() if admin_id else 0
            
            completed_sub = db.query(
                TrainingCompletion.employee_id,
                func.count(TrainingCompletion.id).label("completed_count")
            ).filter(TrainingCompletion.status == "completed").group_by(TrainingCompletion.employee_id).subquery()
            
            reports_sub = db.query(
                ReportedEmail.employee_id,
                func.count(ReportedEmail.id).label("reports_count")
            ).group_by(ReportedEmail.employee_id).subquery()
            
            rewards_sub = db.query(
                Reward.employee_id,
                func.sum(Reward.xp_amount).label("total_xp")
            ).group_by(Reward.employee_id).subquery()
            
            all_rows = db.query(
                Employee.id,
                Employee.risk_score,
                func.coalesce(completed_sub.c.completed_count, 0).label("completed_count"),
                func.coalesce(reports_sub.c.reports_count, 0).label("reports_count"),
                func.coalesce(rewards_sub.c.total_xp, 0).label("total_xp")
            ).outerjoin(completed_sub, Employee.id == completed_sub.c.employee_id
            ).outerjoin(reports_sub, Employee.id == reports_sub.c.employee_id
            ).outerjoin(rewards_sub, Employee.id == rewards_sub.c.employee_id
            ).filter(
                Employee.company_id == company_id,
                Employee.is_active == True
            ).all()
            
            processed = []
            for r_row in all_rows:
                emp_id, r_score, c_count, rep_count, t_xp = r_row
                sec_score = round(100.0 - (r_score or 0.0), 1)
                comp_pct = int((c_count / total_modules) * 100) if total_modules > 0 else 0
                processed.append({
                    "employee_id": emp_id,
                    "security_score": sec_score,
                    "total_xp": int(t_xp) if t_xp else 0,
                    "completion_percentage": comp_pct,
                    "reports_count": rep_count
                })
                
            processed.sort(
                key=lambda x: (x["security_score"], x["total_xp"], x["completion_percentage"], x["reports_count"]),
                reverse=True
            )
            
            for index, item in enumerate(processed, 1):
                if item["employee_id"] == employee_id:
                    leaderboard_rank = index
                    break

        # Generate secure short-lived token
        dashboard_token = secrets.token_urlsafe(32)
        emp.dashboard_token = dashboard_token
        emp.dashboard_token_expires_at = datetime.now() + timedelta(minutes=10)
        db.commit()

        # Fetch company details
        company_name = "Your company"
        if emp.company_id:
            company = db.query(Company).filter(Company.id == emp.company_id).first()
            if company and company.company_name:
                company_name = company.company_name

        learning_tips = [
            "Check the sender address carefully.",
            "Do not click suspicious links.",
            "Report suspicious emails immediately."
        ]

        return {
            "success": True,
            "report_id": str(db_report.id),
            "status": "Reported",
            "subject": email_subject,
            "sender": email_sender,
            "risk_score": analysis["risk_score"],
            "risk_level": analysis["risk_level"],
            "points_added": points_added,
            "employee_score": employee_score,
            "leaderboard_rank": leaderboard_rank,
            "company_name": company_name,
            "learning_tips": learning_tips,
            "dashboard_token": dashboard_token
        }
    except Exception as e:
        db.rollback()
        print("Error processing Gmail report:", str(e))
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error. Please try again later."}
        )

@router.post("/gmail/admin-message")
def gmail_admin_message(req: GmailAdminMessageCreate, db: Session = Depends(get_db)):
    """Ingest a support or feedback message from Gmail side panel and link it to the report."""
    # Validate employee email
    emp = db.query(Employee).filter(func.lower(Employee.email) == req.employee_email.strip().lower()).first()
    if not emp:
        return JSONResponse(status_code=400, content={"success": False, "error": "Employee email not registered."})
        
    # Find the report
    report = db.query(ReportedEmail).filter(ReportedEmail.id == req.report_id).first()
    if not report:
        return JSONResponse(status_code=404, content={"success": False, "error": "Report not found."})
        
    # Determine the company admin
    admin_id = emp.admin_id
    if not admin_id:
        if emp.company_id:
            company = db.query(Company).filter(Company.id == emp.company_id).first()
            if company:
                admin_id = company.admin_id
                
    if not admin_id:
        admin = db.query(User).filter(User.role == "Admin").first()
        if admin:
            admin_id = admin.id

    # Create message
    db_message = Message(
        employee_id=emp.id,
        admin_id=admin_id,
        sender_id=emp.id,
        sender_role="employee",
        sender_name=emp.name or f"{emp.first_name} {emp.last_name}".strip() or "Employee",
        reported_email_id=report.id,
        message_text=req.message,
        is_read=False
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    return {"success": True, "message_id": str(db_message.id)}
