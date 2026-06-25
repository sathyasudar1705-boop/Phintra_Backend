import urllib.request
import json
from sqlalchemy.orm import Session
from app.config import settings
from app.models.employee import Employee
from app.models.campaign import Campaign
from app.models.email_log import EmailLog
from app.models.reported_email import ReportedEmail
from app.models.training import TrainingModule, TrainingCompletion
from app.models.department import Department

def get_admin_summary_context(db: Session, admin_id) -> str:
    # Query counts and statistics scoped to this admin_id
    total_employees = db.query(Employee).filter(Employee.admin_id == admin_id).count()
    
    # Breakdown by department
    dept_stats = []
    departments = db.query(Department).filter(Department.admin_id == admin_id).all()
    for dept in departments:
        count = db.query(Employee).filter(Employee.department_id == dept.id).count()
        dept_stats.append(f"{dept.name}: {count} employees")
    dept_str = ", ".join(dept_stats) if dept_stats else "None"

    total_campaigns = db.query(Campaign).filter(Campaign.admin_id == admin_id).count()
    
    # Campaign status breakdown
    active_campaigns = db.query(Campaign).filter(Campaign.admin_id == admin_id, Campaign.status == "Active").count()
    completed_campaigns = db.query(Campaign).filter(Campaign.admin_id == admin_id, Campaign.status == "Completed").count()
    draft_campaigns = db.query(Campaign).filter(Campaign.admin_id == admin_id, Campaign.status == "Draft").count()

    total_emails_sent = db.query(EmailLog).filter(EmailLog.admin_id == admin_id, EmailLog.status == "Sent").count()
    total_emails_failed = db.query(EmailLog).filter(EmailLog.admin_id == admin_id, EmailLog.status == "Failed").count()

    total_reported = db.query(ReportedEmail).filter(ReportedEmail.admin_id == admin_id).count()
    reported_pending = db.query(ReportedEmail).filter(ReportedEmail.admin_id == admin_id, ReportedEmail.report_status == "Pending").count()
    reported_suspicious = db.query(ReportedEmail).filter(ReportedEmail.admin_id == admin_id, ReportedEmail.report_status == "Suspicious").count()

    total_training_modules = db.query(TrainingModule).filter(TrainingModule.admin_id == admin_id).count()
    
    total_completions = db.query(TrainingCompletion).join(TrainingModule).filter(
        TrainingModule.admin_id == admin_id,
        TrainingCompletion.status == "completed"
    ).count()

    # Risk score average
    employees = db.query(Employee).filter(Employee.admin_id == admin_id).all()
    avg_risk_score = 0.0
    if employees:
        avg_risk_score = sum(emp.risk_score for emp in employees) / len(employees)

    # Awareness score (hypothetical, e.g. 100 - avg_risk_score * 10)
    awareness_score = max(0.0, min(100.0, 100.0 - (avg_risk_score * 10)))

    context = (
        f"Admin Scoped System Data Context:\n"
        f"- Admin ID: {admin_id}\n"
        f"- Total Employees: {total_employees}\n"
        f"- Employees by Department: {dept_str}\n"
        f"- Total Campaigns: {total_campaigns} (Draft: {draft_campaigns}, Active: {active_campaigns}, Completed: {completed_campaigns})\n"
        f"- Emails Sent successfully: {total_emails_sent}\n"
        f"- Emails Failed: {total_emails_failed}\n"
        f"- Total Phishing Emails Reported: {total_reported} (Pending Review: {reported_pending}, Suspicious: {reported_suspicious})\n"
        f"- Total Training Modules Available: {total_training_modules}\n"
        f"- Total Training Modules Completed by Employees: {total_completions}\n"
        f"- Average Employee Risk Score: {avg_risk_score:.2f} (Scale: 0.0 to 10.0)\n"
        f"- Company Awareness Score: {awareness_score:.2f}%\n"
    )
    return context

def ask_gemini(context: str, question: str) -> str:
    import time
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return "Gemini API Key is not configured on the backend. Please add GEMINI_API_KEY to your environment variables."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    prompt = (
        f"You are the Phintra AI Cyber Security Assistant. You assist administrators with security awareness metrics, employee statistics, and campaign analysis using only the context provided. Do not invent any numbers outside the context.\n\n"
        f"{context}\n\n"
        f"User Question: {question}\n\n"
        f"Provide a clear, professional, and helpful response."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    max_retries = 3
    retry_delay = 1.0  # seconds

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                text_response = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return text_response
        except Exception as e:
            is_transient = False
            # HTTP 503 is service unavailable, HTTP 429 is rate limit (often transient demand spikes)
            if hasattr(e, 'code') and e.code in [429, 503]:
                is_transient = True
                
            if is_transient and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue

            err_msg = str(e)
            if hasattr(e, 'read'):
                try:
                    err_msg += " | details: " + e.read().decode('utf-8')
                except Exception:
                    pass
            return f"Error contacting Gemini AI service: {err_msg}"
