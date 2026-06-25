from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from typing import List, Optional
import shutil
import os
import uuid
from datetime import datetime

from app.database import get_db
from app.models.training import TrainingModule, TrainingAssignment, TrainingCompletion, CompletionStatus
from app.models.employee import Employee
from app.models.user import User
from app.schemas.training_schema import (
    TrainingModuleCreate, TrainingModuleUpdate, TrainingModuleResponse,
    TrainingAssignmentCreate, TrainingAssignmentResponse, TrainingCompletionResponse
)
from app.dependencies import get_current_admin, get_current_user

router = APIRouter(tags=["Training"])

# Create directory to store uploaded files
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../uploads/training_videos"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# FEATURE 1: Admin Training Module Creation
@router.post("/training-modules", response_model=TrainingModuleResponse, status_code=status.HTTP_201_CREATED)
def create_training_module(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    duration: int = Form(...),
    difficulty: Optional[str] = Form(None),
    video_url: Optional[str] = Form(None),
    uploaded_video: Optional[UploadFile] = File(None),
    xp_reward: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    # Check duplicate title under this admin
    existing = db.query(TrainingModule).filter(
        TrainingModule.title == title,
        TrainingModule.admin_id == current_admin.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A training module with this title already exists")

    uploaded_path = None
    if uploaded_video:
        file_ext = os.path.splitext(uploaded_video.filename)[1]
        filename = f"{uuid.uuid4().hex}{file_ext}"
        file_location = os.path.join(UPLOAD_DIR, filename)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(uploaded_video.file, buffer)
        uploaded_path = f"/uploads/training_videos/{filename}"

    # Use raw SQL to avoid ORM column-name mapping issues (duration vs duration_minutes)
    new_id = uuid.uuid4()
    
    # Create temporary module container to pass check for: "xp_reward": module.xp_reward if module.xp_reward else 50
    class ModuleContainer:
        def __init__(self, xp_reward):
            self.xp_reward = xp_reward
    module = ModuleContainer(xp_reward)

    db.execute(text("""
        INSERT INTO training_modules
            (id, admin_id, title, description, category, duration_minutes, difficulty, video_url, uploaded_video_url, xp_reward)
        VALUES
            (:id, :admin_id, :title, :description, :category, :duration_minutes, :difficulty, :video_url, :uploaded_video_url, :xp_reward)
    """), {
        "id": new_id,
        "admin_id": current_admin.id,
        "title": title,
        "description": description,
        "category": category,
        "duration_minutes": int(duration),
        "difficulty": difficulty,
        "video_url": video_url,
        "uploaded_video_url": uploaded_path,
        "xp_reward": module.xp_reward if module.xp_reward else 50,
    })
    db.commit()
    module = db.query(TrainingModule).filter(TrainingModule.id == new_id).first()
    return module

@router.get("/training-modules", response_model=List[TrainingModuleResponse])
def list_training_modules(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    return db.query(TrainingModule).filter(TrainingModule.admin_id == current_admin.id).all()

@router.get("/training-modules/{id}", response_model=TrainingModuleResponse)
def get_training_module(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    module = db.query(TrainingModule).filter(
        TrainingModule.id == id,
        TrainingModule.admin_id == current_admin.id
    ).first()
    if not module:
        raise HTTPException(status_code=403, detail="Forbidden or training module not found")
    return module

@router.put("/training-modules/{id}", response_model=TrainingModuleResponse)
def update_training_module(
    id: uuid.UUID,
    module_in: TrainingModuleUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    module = db.query(TrainingModule).filter(
        TrainingModule.id == id,
        TrainingModule.admin_id == current_admin.id
    ).first()
    if not module:
        raise HTTPException(status_code=403, detail="Forbidden or training module not found")

    update_data = module_in.dict(exclude_unset=True)
    # Build raw SQL SET clause to avoid duration vs duration_minutes mismatch
    set_parts = []
    params = {"id": id}
    for key, val in update_data.items():
        col = "duration_minutes" if key == "duration" else key
        set_parts.append(f"{col} = :{col}")
        params[col] = val
    if set_parts:
        db.execute(text(f"UPDATE training_modules SET {', '.join(set_parts)} WHERE id = :id"), params)
        db.commit()
    db.refresh(module)
    return module

@router.delete("/training-modules/{id}", status_code=status.HTTP_200_OK)
def delete_training_module(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    module = db.query(TrainingModule).filter(
        TrainingModule.id == id,
        TrainingModule.admin_id == current_admin.id
    ).first()
    if not module:
        raise HTTPException(status_code=403, detail="Forbidden or training module not found")
    db.delete(module)
    db.commit()
    return {"detail": "Training module successfully deleted"}


# FEATURE 2: Training Assignment and Employee Access
@router.post("/training-modules/{id}/assign", response_model=List[TrainingAssignmentResponse])
def assign_training_module(
    id: uuid.UUID,
    req: TrainingAssignmentCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    # Validate the training module belongs to the logged-in admin
    module = db.query(TrainingModule).filter(
        TrainingModule.id == id,
        TrainingModule.admin_id == current_admin.id
    ).first()
    if not module:
        raise HTTPException(status_code=403, detail="Forbidden or training module not found")

    assignments = []
    if req.assign_all:
        employees = db.query(Employee).filter(Employee.admin_id == current_admin.id).all()
        for emp in employees:
            # Check existing assignment to prevent duplicate
            existing = db.query(TrainingAssignment).filter(
                TrainingAssignment.training_module_id == id,
                TrainingAssignment.employee_id == emp.id
            ).first()
            if not existing:
                a = TrainingAssignment(
                    training_module_id=id,
                    admin_id=current_admin.id,
                    employee_id=emp.id
                )
                db.add(a)
                assignments.append(a)
            else:
                assignments.append(existing)
    elif req.employee_id:
        # Verify employee belongs to current admin
        emp = db.query(Employee).filter(
            Employee.id == req.employee_id,
            Employee.admin_id == current_admin.id
        ).first()
        if not emp:
            raise HTTPException(status_code=400, detail="Employee not found under this admin")
        existing = db.query(TrainingAssignment).filter(
            TrainingAssignment.training_module_id == id,
            TrainingAssignment.employee_id == req.employee_id
        ).first()
        if not existing:
            a = TrainingAssignment(
                training_module_id=id,
                admin_id=current_admin.id,
                employee_id=req.employee_id
            )
            db.add(a)
            assignments.append(a)
        else:
            assignments.append(existing)
    elif req.department_id:
        existing = db.query(TrainingAssignment).filter(
            TrainingAssignment.training_module_id == id,
            TrainingAssignment.department_id == req.department_id
        ).first()
        if not existing:
            a = TrainingAssignment(
                training_module_id=id,
                admin_id=current_admin.id,
                department_id=req.department_id
            )
            db.add(a)
            assignments.append(a)
        else:
            assignments.append(existing)
    elif req.company_id:
        existing = db.query(TrainingAssignment).filter(
            TrainingAssignment.training_module_id == id,
            TrainingAssignment.company_id == req.company_id
        ).first()
        if not existing:
            a = TrainingAssignment(
                training_module_id=id,
                admin_id=current_admin.id,
                company_id=req.company_id
            )
            db.add(a)
            assignments.append(a)
        else:
            assignments.append(existing)
    else:
        raise HTTPException(status_code=400, detail="No assignment target specified")

    db.commit()
    for assign in assignments:
        db.refresh(assign)
    return assignments

@router.get("/employee/training-modules")
def get_employee_training_modules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    emp = db.query(Employee).filter(Employee.email == current_user.email).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")

    assignments = db.query(TrainingAssignment).filter(
        TrainingAssignment.admin_id == emp.admin_id
    ).filter(
        or_(
            TrainingAssignment.employee_id == emp.id,
            TrainingAssignment.department_id == emp.department_id,
            TrainingAssignment.company_id == emp.company_id,
            (TrainingAssignment.employee_id.is_(None)) & (TrainingAssignment.department_id.is_(None)) & (TrainingAssignment.company_id.is_(None))
        )
    ).all()

    module_ids = {a.training_module_id for a in assignments}

    if not module_ids:
        return []

    modules = db.query(TrainingModule).filter(
        TrainingModule.id.in_(module_ids),
        TrainingModule.admin_id == emp.admin_id
    ).all()

    completions = db.query(TrainingCompletion).filter(
        TrainingCompletion.employee_id == emp.id,
        TrainingCompletion.training_module_id.in_(module_ids)
    ).all()
    completions_dict = {c.training_module_id: c.status.value for c in completions}

    res = []
    for mod in modules:
        res.append({
            "id": mod.id,
            "title": mod.title,
            "description": mod.description,
            "category": mod.category,
            "duration": mod.duration,
            "difficulty": mod.difficulty,
            "video_url": mod.video_url,
            "uploaded_video_url": mod.uploaded_video_url,
            "status": completions_dict.get(mod.id, "not_started"),
            "created_at": mod.created_at
        })
    return res

@router.post("/training-modules/{id}/complete", response_model=TrainingCompletionResponse)
def complete_training_module(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    emp = db.query(Employee).filter(Employee.email == current_user.email).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee profile not found")

    assignment = db.query(TrainingAssignment).filter(
        TrainingAssignment.training_module_id == id,
        TrainingAssignment.admin_id == emp.admin_id
    ).filter(
        or_(
            TrainingAssignment.employee_id == emp.id,
            TrainingAssignment.department_id == emp.department_id,
            TrainingAssignment.company_id == emp.company_id,
            (TrainingAssignment.employee_id.is_(None)) & (TrainingAssignment.department_id.is_(None)) & (TrainingAssignment.company_id.is_(None))
        )
    ).first()

    if not assignment:
        raise HTTPException(status_code=403, detail="You do not have access to this training module")

    completion = db.query(TrainingCompletion).filter(
        TrainingCompletion.training_module_id == id,
        TrainingCompletion.employee_id == emp.id
    ).first()

    from app.utils.scoring import log_activity_event
    from app.models.campaign import CampaignRecipient

    if not completion:
        completion = TrainingCompletion(
            training_module_id=id,
            employee_id=emp.id,
            status=CompletionStatus.COMPLETED,
            completed_at=datetime.utcnow()
        )
        db.add(completion)
    else:
        completion.status = CompletionStatus.COMPLETED
        completion.completed_at = datetime.utcnow()

    # Update recipient training progress
    recipient = db.query(CampaignRecipient).filter(
        CampaignRecipient.employee_id == emp.id
    ).order_by(CampaignRecipient.created_at.desc()).first()
    if recipient:
        recipient.training_completed_at = datetime.utcnow()
        recipient.status = "Completed Training"

    log_activity_event(db, emp.id, "training_completed", event_value=str(id))

    db.commit()
    db.refresh(completion)
    return completion
