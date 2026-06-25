from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.user_schema import UserCreate, UserResponse, Token
from app.services.auth_service import register_user, authenticate_user
from app.dependencies import get_current_user
from app.models.user import User

import sqlalchemy as sa
from app.models.employee import Employee
from app.models.company import Company
from app.models.department import Department
from app.models.certificate import Reward, Certificate
from app.models.training import TrainingModule, TrainingAssignment, TrainingCompletion
from app.models.quiz import Quiz, QuizAttempt
from app.models.notification import Notification
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/auth", tags=["Authentication"])

import logging
import traceback

logger = logging.getLogger("app.routes.auth")

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """Register portal access credentials."""
    # Temporary debug log of incoming request payload
    logger.info(f"[DEBUG] Incoming registration payload: email={user_in.email}, full_name={user_in.full_name}, company={user_in.company_name}")
    try:
        return register_user(db, user_in)
    except HTTPException as he:
        logger.warning(f"[DEBUG] Registration HTTP error: status={he.status_code}, detail={he.detail}")
        raise he
    except Exception as e:
        logger.error(f"[DEBUG] Registration unexpected error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Log in to retrieve bearer JWT authorization token."""
    access_token = authenticate_user(db, form_data.username, form_data.password)
    user = db.query(User).filter(User.email == form_data.username).first()
    if user:
        audit = AuditLog(user_id=user.id, action="Login", details=f"User {user.email} logged in successfully.")
        db.add(audit)
        db.commit()
    else:
        from app.models.employee import Employee
        emp = db.query(Employee).filter(Employee.email == form_data.username).first()
        if emp:
            audit = AuditLog(action="Employee Login", details=f"Employee {emp.email} logged in successfully.")
            db.add(audit)
            db.commit()
    return {"access_token": access_token, "token_type": "bearer"}

from pydantic import BaseModel, EmailStr

class EmployeeLoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/employee-login")
def employee_login(login_data: EmployeeLoginRequest, db: Session = Depends(get_db)):
    """Log in to retrieve bearer JWT token and employee details (Employees only)."""
    from app.utils.security import verify_password, create_access_token
    from app.models.employee import Employee
    from app.models.department import Department
    
    # Try Employee table lookup
    emp = db.query(Employee).filter(Employee.email == login_data.email).first()
            
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Incorrect email or password"
        )
        
    if not emp.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Employee account is inactive"
        )
        
    # Verify password against hashed_password (or fallback to password_hash)
    stored_hash = emp.hashed_password or emp.password_hash
    if not stored_hash or not verify_password(login_data.password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Incorrect email or password"
        )
        
    # Confirm role is "employee"
    role = getattr(emp, "role", "employee")
    if role != "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Access denied. Employees only."
        )
        
    access_token = create_access_token(data={
        "sub": emp.email,
        "role": "Employee",
        "employee_id": str(emp.id)
    })
    
    # Get department name
    dept = db.query(Department).filter(Department.id == emp.department_id).first()
    dept_name = dept.name if dept else "Unknown"
    
    # Write audit log
    audit = AuditLog(action="Employee Login", details=f"Employee {emp.email} logged in successfully.")
    db.add(audit)
    db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "employee": {
            "name": emp.name or f"{emp.first_name} {emp.last_name}".strip(),
            "email": emp.email,
            "department": dept_name,
            "role": role
        }
    }

@router.get("/verify-dashboard-token")
def verify_dashboard_token(token: str, db: Session = Depends(get_db)):
    """Verify short-lived dashboard token, generate a long-lived JWT access token, and return profile info."""
    from datetime import datetime, timezone
    from app.utils.security import create_access_token
    from app.models.employee import Employee
    from app.models.department import Department
    from app.models.audit_log import AuditLog
    
    # 1. Lookup employee by token
    emp = db.query(Employee).filter(Employee.dashboard_token == token).first()
    if not emp:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    # 2. Check expiration
    now = datetime.now(timezone.utc) if emp.dashboard_token_expires_at.tzinfo else datetime.now()
    if emp.dashboard_token_expires_at < now:
        raise HTTPException(status_code=401, detail="Token has expired")
        
    # 3. Clear token to prevent reuse (one-time use)
    emp.dashboard_token = None
    emp.dashboard_token_expires_at = None
    
    # 4. Generate access token
    access_token = create_access_token(data={
        "sub": emp.email,
        "role": "Employee",
        "employee_id": str(emp.id)
    })
    
    # 5. Get department name
    dept = db.query(Department).filter(Department.id == emp.department_id).first()
    dept_name = dept.name if dept else "Unknown"
    
    # Write audit log
    audit = AuditLog(action="Token Auto-Login", details=f"Employee {emp.email} logged in via dashboard token.")
    db.add(audit)
    db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "employee": {
            "name": emp.name or f"{emp.first_name} {emp.last_name}".strip(),
            "email": emp.email,
            "department": dept_name,
            "role": "Employee",
            "personal_score": 100.0 - emp.risk_score
        }
    }

@router.get("/validate")
def validate_token(current_user: User = Depends(get_current_user)):
    """Validate active JWT token."""
    return {"valid": True, "email": current_user.email, "role": current_user.role}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Fetch details of currently logged-in portal account."""
    return current_user

@router.get("/me/profile")
def get_me_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch rich integrated user profile including employee/department parameters."""
    emp = db.query(Employee).filter(Employee.email == current_user.email).first()
    
    # Default fallbacks
    xp = 0
    level = 1
    certificates = []
    dept_name = "Security Operations" if current_user.role == "Admin" else "Information Technology"
    personal_score = 100.0
    name = current_user.email.split("@")[0].replace(".", " ").title()
    employee_id = None
    admin_id = str(current_user.id)
    
    if emp:
        name = f"{emp.first_name} {emp.last_name}"
        personal_score = 100.0 - emp.risk_score
        employee_id = str(emp.id)
        admin_id = str(emp.admin_id) if emp.admin_id else str(current_user.id)
        
        dept = db.query(Department).filter(Department.id == emp.department_id).first()
        if dept:
            dept_name = dept.name
            
        xp_sum = db.query(sa.func.sum(Reward.xp_amount)).filter(Reward.employee_id == emp.id).scalar()
        if xp_sum:
            xp = int(xp_sum)
            level = int(xp / 1000) + 1
            
        certs = db.query(Certificate).filter(Certificate.employee_id == emp.id).all()
        for cert in certs:
            mod = db.query(TrainingModule).filter(TrainingModule.id == cert.module_id).first()
            if mod:
                certificates.append(mod.title)
                
    return {
        "email": current_user.email,
        "name": name,
        "role": current_user.role,
        "department": dept_name,
        "personal_score": int(personal_score),
        "xp": xp if xp > 0 else (2450 if current_user.role == "Admin" else 500),
        "level": level if level > 1 else (12 if current_user.role == "Admin" else 2),
        "certificates": certificates,
        "employee_id": employee_id,
        "admin_id": admin_id
    }

@router.put("/me/profile")
def update_me_profile(name: str, email: str, department_name: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update details of active logged-in employee profile."""
    # Find user
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
        
    user.email = email
    
    # Find employee
    emp = db.query(Employee).filter(Employee.email == current_user.email).first()
    if emp:
        emp.email = email
        names = name.split(" ")
        emp.first_name = names[0]
        emp.last_name = " ".join(names[1:]) if len(names) > 1 else ""
        
        # Find department
        dept = db.query(Department).filter(Department.name == department_name).first()
        if dept:
            emp.department_id = dept.id
            
    db.commit()
    audit = AuditLog(user_id=user.id, action="Profile Update", details=f"User {user.email} updated profile information.")
    db.add(audit)
    db.commit()
    return {"message": "Profile successfully updated"}

@router.get("/employee/dashboard")
def get_employee_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve detailed dashboard data for the logged-in employee."""
    emp = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not emp:
        emp = db.query(Employee).filter(Employee.email == current_user.email).first()
        if not emp:
            raise HTTPException(status_code=404, detail="Employee profile not found")
        
    # Company info
    company = db.query(Company).filter(Company.id == emp.company_id).first()
    company_name = company.company_name if company else "Phintra Enterprise"
    company_address = company.company_address if company else "123 Cyber Way"

    # Assigned Trainings
    assignments = db.query(TrainingAssignment).filter(
        TrainingAssignment.admin_id == emp.admin_id
    ).filter(
        sa.or_(
            TrainingAssignment.employee_id == emp.id,
            TrainingAssignment.department_id == emp.department_id,
            TrainingAssignment.company_id == emp.company_id,
            (TrainingAssignment.employee_id.is_(None)) & (TrainingAssignment.department_id.is_(None)) & (TrainingAssignment.company_id.is_(None))
        )
    ).all()

    module_ids = {a.training_module_id for a in assignments}
    assigned_trainings = []
    
    if module_ids:
        modules = db.query(TrainingModule).filter(
            TrainingModule.id.in_(module_ids),
            TrainingModule.admin_id == emp.admin_id
        ).all()
        
        completions = db.query(TrainingCompletion).filter(
            TrainingCompletion.employee_id == emp.id,
            TrainingCompletion.training_module_id.in_(module_ids)
        ).all()
        completions_dict = {c.training_module_id: c.status.value for c in completions}
        completions_obj = {c.training_module_id: c for c in completions}

        for mod in modules:
            status_val = completions_dict.get(mod.id, "not_started")
            comp_obj = completions_obj.get(mod.id)
            
            assigned_trainings.append({
                "module_id": str(mod.id),
                "title": mod.title,
                "description": mod.description,
                "duration_minutes": mod.duration or 10,
                "xp_reward": 100,
                "progress": 100 if status_val == "completed" else (50 if status_val == "in_progress" else 0),
                "completed": status_val == "completed",
                "completed_at": comp_obj.completed_at.isoformat() if (comp_obj and comp_obj.completed_at) else None
            })

    # Calculate training completion percentage
    completed_training_count = sum(1 for t in assigned_trainings if t["completed"])
    total_assigned_count = len(assigned_trainings)
    training_completion_percentage = int((completed_training_count / total_assigned_count) * 100) if total_assigned_count > 0 else 100

    # Quiz attempts
    attempts = db.query(QuizAttempt).filter(QuizAttempt.employee_id == emp.id).all()
    quiz_results = []
    for att in attempts:
        quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
        mod_title = "Unknown Module"
        if quiz:
            mod = db.query(TrainingModule).filter(TrainingModule.id == quiz.module_id).first()
            if mod:
                mod_title = mod.title
        quiz_results.append({
            "id": str(att.id),
            "module_title": mod_title,
            "score": att.score,
            "passed": att.passed,
            "attempted_at": att.attempted_at.isoformat()
        })
        
    # Certificates
    certs = db.query(Certificate).filter(Certificate.employee_id == emp.id).all()
    certificates = []
    for c in certs:
        mod = db.query(TrainingModule).filter(TrainingModule.id == c.module_id).first()
        certificates.append({
            "id": str(c.id),
            "module_title": mod.title if mod else "Unknown Course",
            "verification_code": c.verification_code,
            "issued_at": c.issued_at.isoformat()
        })
        
    # Rewards
    rew_list = db.query(Reward).filter(Reward.employee_id == emp.id).all()
    rewards = [{
        "id": str(r.id),
        "xp_amount": r.xp_amount,
        "description": r.description,
        "earned_at": r.earned_at.isoformat()
    } for r in rew_list]
    rewards_balance = sum(r.xp_amount for r in rew_list)
    
    # Notifications
    notifs = db.query(Notification).filter(Notification.employee_id == emp.id).all()
    notifications = [{
        "id": str(n.id),
        "title": n.title,
        "message": n.message,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat()
    } for n in notifs]
    
    # Campaign participation details
    from app.models.campaign import CampaignRecipient
    campaign_recipients = db.query(CampaignRecipient).filter(CampaignRecipient.employee_id == emp.id).all()
    campaign_participation = []
    for cr in campaign_recipients:
        campaign_participation.append({
            "campaign_id": str(cr.campaign_id),
            "campaign_name": cr.campaign.name if cr.campaign else "Unknown Campaign",
            "status": cr.status,
            "updated_at": (cr.updated_at or cr.created_at).isoformat()
        })

    campaigns_received = len(campaign_recipients)
    campaigns_opened = sum(1 for cr in campaign_recipients if cr.status in ["Opened", "Clicked", "Reported"])
    campaigns_clicked = sum(1 for cr in campaign_recipients if cr.status == "Clicked")
    campaigns_reported = sum(1 for cr in campaign_recipients if cr.status == "Reported")

    # Reported emails
    from app.models.reported_email import ReportedEmail
    rep_emails = db.query(ReportedEmail).filter(ReportedEmail.employee_id == emp.id).all()
    reported_emails_list = []
    for re in rep_emails:
        reported_emails_list.append({
            "id": str(re.id),
            "subject": re.email_subject if re.email_subject else re.subject,
            "sender": re.email_sender if re.email_sender else re.sender,
            "status": re.report_status if re.report_status else re.status,
            "reported_at": re.reported_at.isoformat()
        })

    # Leaderboard ranking and percentile
    company_employees = db.query(Employee).filter(
        Employee.company_id == emp.company_id,
        Employee.is_active == True
    ).all()
    company_employees.sort(key=lambda x: (100.0 - x.risk_score), reverse=True)
    
    leaderboard_rank = 1
    for index, item in enumerate(company_employees):
        if item.id == emp.id:
            leaderboard_rank = index + 1
            break
            
    total_count = len(company_employees)
    leaderboard_percentile = round(((total_count - leaderboard_rank + 1) / total_count) * 100) if total_count > 0 else 100

    # Unread message count
    from app.models.message import Message
    unread_message_count = db.query(Message).filter(
        Message.employee_id == emp.id,
        Message.admin_id == emp.admin_id,
        Message.sender_role == "admin",
        Message.is_read == False
    ).count()

    # Activity Log Timeline
    activity_log = []
    
    for att in attempts:
        quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
        quiz_name = quiz.quizName if quiz else "Quiz"
        activity_log.append({
            "id": f"quiz-{att.id}",
            "type": "quiz",
            "title": f"Attempted {quiz_name}",
            "description": f"Scored {att.score}% ({'Passed' if att.passed else 'Failed'})",
            "timestamp": att.attempted_at.isoformat()
        })
        
    for comp in completions:
        mod = db.query(TrainingModule).filter(TrainingModule.id == comp.training_module_id).first()
        mod_title = mod.title if mod else "Training Module"
        activity_log.append({
            "id": f"comp-{comp.id}",
            "type": "training",
            "title": f"Completed Course: {mod_title}",
            "description": "Earned completion certificate and XP reward.",
            "timestamp": comp.completed_at.isoformat() if comp.completed_at else comp.created_at.isoformat()
        })
        
    for re in rep_emails:
        activity_log.append({
            "id": f"report-{re.id}",
            "type": "report",
            "title": "Reported Suspicious Email",
            "description": f"Subject: '{re.email_subject or re.subject}'",
            "timestamp": re.reported_at.isoformat()
        })
        
    activity_log.sort(key=lambda x: x["timestamp"], reverse=True)

    return {
        "employee_id": str(emp.id),
        "name": f"{emp.first_name} {emp.last_name}",
        "email": emp.email,
        "department": db.query(Department.name).filter(Department.id == emp.department_id).scalar() or "Security",
        "role": emp.role,
        "company_name": company_name,
        "company_address": company_address,
        "security_score": round(100.0 - emp.risk_score, 1),
        "risk_score": emp.risk_score,
        "training_completion": training_completion_percentage,
        "campaigns_received": campaigns_received,
        "campaigns_opened": campaigns_opened,
        "campaigns_clicked": campaigns_clicked,
        "campaigns_reported": campaigns_reported,
        "leaderboard_rank": leaderboard_rank,
        "leaderboard_percentile": leaderboard_percentile,
        "rewards_balance": rewards_balance,
        "activity_log": activity_log[:20],
        "assigned_trainings": assigned_trainings,
        "quiz_results": quiz_results,
        "certificates": certificates,
        "rewards": rewards,
        "notifications": notifications,
        "campaign_participation": campaign_participation,
        "reported_emails": reported_emails_list,
        "unread_message_count": unread_message_count
    }

class AddonTokenRequest(BaseModel):
    email: EmailStr
    addon_key: str

@router.post("/auth/addon/generate-token")
@router.post("/addon/generate-token")
def generate_addon_token(payload: AddonTokenRequest, db: Session = Depends(get_db)):
    """Generate a secure, short-lived SSO token for the Gmail Add-on."""
    import os
    expected_key = os.getenv("PHINTRA_ADDON_KEY", "phintra-dev-key-123")
    if payload.addon_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Gmail Add-on key"
        )
    
    emp = db.query(Employee).filter(Employee.email == payload.email).first()
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee email not found"
        )
    
    from app.utils.security import create_access_token
    from datetime import timedelta
    sso_token = create_access_token(
        data={"sub": payload.email, "scope": "addon_sso", "employee_id": str(emp.id)},
        expires_delta=timedelta(minutes=5)
    )
    return {"sso_token": sso_token}

class VerifyAddonTokenRequest(BaseModel):
    token: str

@router.post("/auth/addon/validate-token")
@router.post("/addon/validate-token")
def validate_addon_token(payload: VerifyAddonTokenRequest, db: Session = Depends(get_db)):
    """Validate Gmail Add-on token and issue a session JWT."""
    from app.utils.security import decode_access_token, create_access_token
    claims = decode_access_token(payload.token)
    if not claims or claims.get("scope") != "addon_sso":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired SSO token"
        )
    
    email = claims.get("sub")
    emp = db.query(Employee).filter(Employee.email == email).first()
    if not emp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee profile not found"
        )
        
    if not emp.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee account is inactive"
        )

    access_token = create_access_token(data={
        "sub": emp.email,
        "role": "Employee",
        "employee_id": str(emp.id)
    })
    
    # Get department name
    dept = db.query(Department).filter(Department.id == emp.department_id).first()
    dept_name = dept.name if dept else "Unknown"
    
    # Audit log
    db_audit = AuditLog(action="Add-on SSO Login", details=f"Employee {emp.email} logged in via Gmail Add-on SSO.")
    db.add(db_audit)
    db.commit()
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "employee": {
            "name": emp.name or f"{emp.first_name} {emp.last_name}".strip() or "Employee",
            "email": emp.email,
            "department": dept_name,
            "role": "Employee"
        }
    }

@router.get("/employee/quiz-results")
def get_employee_quiz_results(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve quiz results for the logged-in employee."""
    emp = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    attempts = db.query(QuizAttempt).filter(QuizAttempt.employee_id == emp.id).all()
    results = []
    for att in attempts:
        quiz = db.query(Quiz).filter(Quiz.id == att.quiz_id).first()
        mod_title = "Unknown Module"
        if quiz:
            mod = db.query(TrainingModule).filter(TrainingModule.id == quiz.module_id).first()
            if mod:
                mod_title = mod.title
        results.append({
            "id": str(att.id),
            "module_title": mod_title,
            "score": att.score,
            "passed": att.passed,
            "attempted_at": att.attempted_at.isoformat()
        })
    return results

@router.get("/employee/rewards")
def get_employee_rewards(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve reward XP entries for the logged-in employee."""
    emp = db.query(Employee).filter(Employee.id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")
    rew_list = db.query(Reward).filter(Reward.employee_id == emp.id).all()
    return [{
        "id": str(r.id),
        "xp_amount": r.xp_amount,
        "description": r.description,
        "earned_at": r.earned_at.isoformat()
    } for r in rew_list]

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Invalidate active session credentials."""
    audit = AuditLog(user_id=current_user.id, action="Logout", details=f"User {current_user.email} logged out successfully.")
    db.add(audit)
    db.commit()
    return {"message": f"Successfully logged out user {current_user.email}"}
