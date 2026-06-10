from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.training import TrainingModule, TrainingAssignment
from app.models.employee import Employee
from app.models.user import User
from app.schemas.training_schema import (
    TrainingModuleCreate, TrainingModuleUpdate, TrainingModuleResponse,
    TrainingAssignmentResponse, TrainingAssignBulkRequest
)
from app.utils.dependencies import require_manager, require_employee
from app.models.audit_log import AuditLog
from uuid import UUID
from typing import List, Optional

router = APIRouter(tags=["Training"])

@router.get("/training-assignments", response_model=List[TrainingAssignmentResponse])
def list_training_assignments(employee_id: Optional[UUID] = None, db: Session = Depends(get_db), current_user: User = Depends(require_employee)):
    """List training assignments (Employees, Managers, Admins)."""
    query = db.query(TrainingAssignment)
    if employee_id:
        query = query.filter(TrainingAssignment.employee_id == employee_id)
    return query.all()

@router.get("/training-modules", response_model=List[TrainingModuleResponse])
def list_training_modules(db: Session = Depends(get_db), current_user: User = Depends(require_employee)):
    """List all course catalog training modules (Employees, Managers, Admins)."""
    return db.query(TrainingModule).all()

@router.post("/training-modules", response_model=TrainingModuleResponse, status_code=status.HTTP_201_CREATED)
def create_training_module(module_in: TrainingModuleCreate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Create a new training module (Managers & Admins)."""
    existing = db.query(TrainingModule).filter(TrainingModule.title == module_in.title).first()
    if existing:
        raise HTTPException(status_code=400, detail="A module with this title already exists")
        
    db_mod = TrainingModule(**module_in.dict())
    db.add(db_mod)
    db.commit()
    db.refresh(db_mod)
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Training Module Creation", details=f"Created course module: {db_mod.title}")
    db.add(audit)
    db.commit()
    return db_mod

@router.put("/training-modules/{id}", response_model=TrainingModuleResponse)
def update_training_module(id: UUID, module_in: TrainingModuleUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Modify details of training module (Managers & Admins)."""
    mod = db.query(TrainingModule).filter(TrainingModule.id == id).first()
    if not mod:
        raise HTTPException(status_code=404, detail="Training module not found")
        
    update_data = module_in.dict(exclude_unset=True)
    for key, val in update_data.items():
        setattr(mod, key, val)
        
    db.commit()
    db.refresh(mod)
    return mod

@router.delete("/training-modules/{id}", status_code=status.HTTP_200_OK)
def delete_training_module(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Delete training module (Managers & Admins)."""
    mod = db.query(TrainingModule).filter(TrainingModule.id == id).first()
    if not mod:
        raise HTTPException(status_code=404, detail="Training module not found")
    db.delete(mod)
    db.commit()
    return {"detail": "Training module successfully deleted"}

@router.post("/training-modules/{id}/assign", response_model=List[TrainingAssignmentResponse])
def assign_training_module(id: UUID, req: TrainingAssignBulkRequest, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Assign training module to multiple employee target accounts (Managers & Admins)."""
    mod = db.query(TrainingModule).filter(TrainingModule.id == id).first()
    if not mod:
        raise HTTPException(status_code=404, detail="Training module not found")
        
    results = []
    for emp_id in req.employee_ids:
        # Verify employee
        emp = db.query(Employee).filter(Employee.id == emp_id).first()
        if not emp:
            continue
            
        # Verify not already assigned
        existing = db.query(TrainingAssignment).filter(
            TrainingAssignment.module_id == id,
            TrainingAssignment.employee_id == emp_id
        ).first()
        
        if existing:
            results.append(existing)
            continue
            
        assignment = TrainingAssignment(employee_id=emp_id, module_id=id)
        db.add(assignment)
        results.append(assignment)
        
    db.commit()
    for assign in results:
        db.refresh(assign)
        
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Training Assignment", details=f"Assigned course {mod.title} to {len(results)} target accounts")
    db.add(audit)
    db.commit()
    return results
