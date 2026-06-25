from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.department import Department
from app.models.employee import Employee
from app.models.audit_log import SecurityScore
from app.schemas.department_schema import DepartmentCreate, DepartmentUpdate, DepartmentResponse, DepartmentDetailResponse
from app.dependencies import require_manager, get_user_admin_id, get_user_company_id
from app.models.audit_log import AuditLog
from app.models.user import User
from uuid import UUID
from typing import List

router = APIRouter(prefix="/departments", tags=["Departments"])

@router.get("", response_model=List[DepartmentDetailResponse])
def list_departments(db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """List all departments with headcount and average risk rating (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)

    departments = db.query(Department).filter(
        (Department.company_id == company_id) | (Department.admin_id == admin_id)
    ).all()
    results = []
    
    for dept in departments:
        # Calculate headcount
        employees = db.query(Employee).filter(
            Employee.department_id == dept.id,
            (Employee.company_id == company_id) | (Employee.admin_id == admin_id)
        ).all()
        headcount = len(employees)
        
        # Calculate average risk score
        avg_risk = 0.0
        if headcount > 0:
            avg_risk = sum(e.risk_score for e in employees) / headcount
            
        detail = DepartmentDetailResponse.from_orm(dept)
        detail.employee_count = headcount
        detail.avg_risk_score = round(avg_risk, 1)
        results.append(detail)
        
    return results

@router.get("/{id}", response_model=DepartmentResponse)
def get_department(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Get single department details by UUID (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)

    dept = db.query(Department).filter(
        Department.id == id,
        (Department.company_id == company_id) | (Department.admin_id == admin_id)
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return dept

@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(dept_in: DepartmentCreate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Add a new department (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)

    if not dept_in.name or not dept_in.name.strip():
        raise HTTPException(status_code=400, detail="Department name is required")
        
    existing_dept = db.query(Department).filter(
        Department.name == dept_in.name.strip(),
        (Department.company_id == company_id) | (Department.admin_id == admin_id)
    ).first()
    if existing_dept:
        raise HTTPException(status_code=400, detail="Department name already exists")
        
    db_dept = Department(
        name=dept_in.name.strip(),
        description=dept_in.description,
        manager_id=dept_in.manager_id,
        risk_score=dept_in.risk_score if dept_in.risk_score is not None else 0,
        training_completion=dept_in.training_completion if dept_in.training_completion is not None else 0,
        company_id=company_id,
        admin_id=admin_id
    )
    db.add(db_dept)
    db.commit()
    db.refresh(db_dept)
    
    # Store initial historical score
    score_entry = SecurityScore(department_id=db_dept.id, score=100.0)
    db.add(score_entry)
    db.commit()
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Department Creation", details=f"Created department: {db_dept.name}")
    db.add(audit)
    db.commit()
    
    return db_dept

@router.put("/{id}", response_model=DepartmentResponse)
def update_department(id: UUID, dept_in: DepartmentUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Modify department details (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)

    dept = db.query(Department).filter(
        Department.id == id,
        (Department.company_id == company_id) | (Department.admin_id == admin_id)
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
        
    if dept_in.name is not None:
        name_val = dept_in.name.strip()
        if not name_val:
            raise HTTPException(status_code=400, detail="Department name cannot be empty")
        existing_dept = db.query(Department).filter(
            Department.name == name_val,
            Department.id != id,
            (Department.company_id == company_id) | (Department.admin_id == admin_id)
        ).first()
        if existing_dept:
            raise HTTPException(status_code=400, detail="Department name already exists")
        dept.name = name_val
        
    if dept_in.description is not None:
        dept.description = dept_in.description
        
    if dept_in.manager_id is not None:
        dept.manager_id = dept_in.manager_id
    elif "manager_id" in dept_in.dict(exclude_unset=True):
        # Allow explicit nulling
        dept.manager_id = None
        
    if dept_in.risk_score is not None:
        dept.risk_score = dept_in.risk_score
        
    if dept_in.training_completion is not None:
        dept.training_completion = dept_in.training_completion

    if hasattr(dept_in, "company_id") and dept_in.company_id is not None:
        dept.company_id = dept_in.company_id
        
    db.commit()
    db.refresh(dept)
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Department Modification", details=f"Modified department: {dept.name}")
    db.add(audit)
    db.commit()
    
    return dept

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_department(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Delete a department (Managers & Admins)."""
    admin_id = get_user_admin_id(db, current_user)
    company_id = get_user_company_id(db, current_user)

    dept = db.query(Department).filter(
        Department.id == id,
        (Department.company_id == company_id) | (Department.admin_id == admin_id)
    ).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    dept_name = dept.name
    db.delete(dept)
    db.commit()
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Department Deletion", details=f"Deleted department: {dept_name}")
    db.add(audit)
    db.commit()
    
    return {"detail": "Department successfully deleted"}
