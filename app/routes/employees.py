from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.employee import Employee
from app.models.department import Department
from app.models.audit_log import SecurityScore
from app.schemas.employee_schema import EmployeeCreate, EmployeeUpdate, EmployeeResponse, EmployeeDetailResponse
from app.utils.dependencies import require_manager, require_admin
from app.models.audit_log import AuditLog
from app.models.user import User
from uuid import UUID
from typing import List, Optional

router = APIRouter(prefix="/employees", tags=["Employees"])

@router.get("", response_model=List[EmployeeDetailResponse])
def list_employees(
    department_id: Optional[UUID] = Query(None),
    status_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager)
):
    """List employees with optional filters (Managers & Admins)."""
    query = db.query(Employee).filter(Employee.admin_id == current_user.id)
    
    if department_id:
        query = query.filter(Employee.department_id == department_id)
    if status_filter:
        query = query.filter(Employee.status == status_filter)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Employee.first_name.ilike(search_pattern)) | 
            (Employee.last_name.ilike(search_pattern)) | 
            (Employee.email.ilike(search_pattern))
        )
        
    employees = query.all()
    
    # Enrich with department name
    enriched_results = []
    for emp in employees:
        dept = db.query(Department).filter(Department.id == emp.department_id).first()
        enriched = EmployeeDetailResponse.from_orm(emp)
        enriched.department_name = dept.name if dept else "Unknown"
        enriched.has_password = bool(emp.password_hash)
        enriched_results.append(enriched)
        
    return enriched_results

@router.get("/{id}", response_model=EmployeeResponse)
def get_employee(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Get single employee profile by UUID (Managers & Admins)."""
    emp = db.query(Employee).filter(Employee.id == id, Employee.admin_id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp

@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee(emp_in: EmployeeCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    """Create a new employee profile (Admins only)."""
    # Reject duplicate emails globally
    existing_emp = db.query(Employee).filter(Employee.email == emp_in.email).first()
    if existing_emp:
        raise HTTPException(status_code=400, detail="Employee email already registered")
        
    existing_user = db.query(User).filter(User.email == emp_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email is already in use by a portal user")
        
    # Verify department exists
    dept = db.query(Department).filter(Department.id == emp_in.department_id).first()
    if not dept:
        raise HTTPException(status_code=400, detail="Department does not exist")
        
    emp_data = emp_in.dict(exclude={"password", "role"})
    
    # Handle name and first/last name alignment for backward compatibility
    if emp_in.name:
        parts = emp_in.name.strip().split(" ")
        first_name = parts[0]
        last_name = " ".join(parts[1:]) if len(parts) > 1 else "Employee"
        emp_data["first_name"] = first_name
        emp_data["last_name"] = last_name
    else:
        first_name = emp_in.first_name or "Unknown"
        last_name = emp_in.last_name or "Employee"
        emp_data["name"] = f"{first_name} {last_name}".strip()
        emp_data["first_name"] = first_name
        emp_data["last_name"] = last_name

    db_emp = Employee(**emp_data)
    
    if emp_in.password:
        from app.utils.security import hash_password
        hashed = hash_password(emp_in.password)
        db_emp.hashed_password = hashed
        db_emp.password_hash = hashed
        
    db_emp.role = "employee"
    db_emp.created_by = current_user.id
    db_emp.admin_id = current_user.id
    
    db.add(db_emp)
    db.commit()
    db.refresh(db_emp)
    
    # Store initial historical score
    score_entry = SecurityScore(employee_id=db_emp.id, score=(100.0 - db_emp.risk_score))
    db.add(score_entry)
    db.commit()
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Employee Creation", details=f"Created employee: {db_emp.name or (db_emp.first_name + ' ' + db_emp.last_name)}")
    db.add(audit)
    db.commit()
    
    return db_emp

@router.put("/{id}", response_model=EmployeeResponse)
def update_employee(id: UUID, emp_in: EmployeeUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Update details of employee profile (Managers & Admins)."""
    emp = db.query(Employee).filter(Employee.id == id, Employee.admin_id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
        
    update_data = emp_in.dict(exclude_unset=True, exclude={"password"})
    
    # Verify department exists if being updated
    if "department_id" in update_data and update_data["department_id"]:
        dept = db.query(Department).filter(Department.id == update_data["department_id"]).first()
        if not dept:
            raise HTTPException(status_code=400, detail="Department does not exist")
            
    for key, val in update_data.items():
        setattr(emp, key, val)
        
    if emp_in.password:
        from app.utils.security import hash_password
        emp.password_hash = hash_password(emp_in.password)
        
    db.commit()
    db.refresh(emp)
    
    # Store updated historical score if risk score changed
    if "risk_score" in update_data:
        score_entry = SecurityScore(employee_id=emp.id, score=(100.0 - emp.risk_score))
        db.add(score_entry)
        db.commit()
        
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Employee Modification", details=f"Modified employee: {emp.first_name} {emp.last_name}")
    db.add(audit)
    db.commit()
    
    return emp

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_employee(id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_manager)):
    """Remove an employee profile from database (Managers & Admins)."""
    emp = db.query(Employee).filter(Employee.id == id, Employee.admin_id == current_user.id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp_name = f"{emp.first_name} {emp.last_name}"
    db.delete(emp)
    db.commit()
    
    # Audit log
    audit = AuditLog(user_id=current_user.id, action="Employee Deletion", details=f"Deleted employee: {emp_name}")
    db.add(audit)
    db.commit()
    
    return {"detail": "Employee successfully deleted"}
