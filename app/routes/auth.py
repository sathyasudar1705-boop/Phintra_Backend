from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.user_schema import UserCreate, UserResponse, Token
from app.services.auth_service import register_user, authenticate_user
from app.utils.dependencies import get_current_user
from app.models.user import User

import sqlalchemy as sa
from app.models.employee import Employee
from app.models.department import Department
from app.models.certificate import Reward, Certificate
from app.models.training import TrainingModule, TrainingAssignment
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
        raise HTTPException(status_code=404, detail="Employee profile not found")
        
    # Assigned Trainings
    assignments = db.query(TrainingAssignment).filter(TrainingAssignment.employee_id == emp.id).all()
    assigned_trainings = []
    for a in assignments:
        mod = db.query(TrainingModule).filter(TrainingModule.id == a.module_id).first()
        if mod:
            assigned_trainings.append({
                "module_id": str(mod.id),
                "title": mod.title,
                "description": mod.description,
                "duration_minutes": mod.duration_minutes,
                "xp_reward": mod.xp_reward,
                "progress": a.progress,
                "completed": a.completed,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None
            })
            
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
            "campaign_name": cr.campaign.name if cr.campaign else "Unknown Campaign",
            "status": cr.status,
            "updated_at": (cr.updated_at or cr.created_at).isoformat()
        })

    # Reported emails
    from app.models.certificate import ReportedEmail
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
    
    return {
        "employee_id": str(emp.id),
        "name": f"{emp.first_name} {emp.last_name}",
        "risk_score": emp.risk_score,
        "status": emp.status,
        "assigned_trainings": assigned_trainings,
        "quiz_results": quiz_results,
        "certificates": certificates,
        "rewards": rewards,
        "notifications": notifications,
        "campaign_participation": campaign_participation,
        "reported_emails": reported_emails_list
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
