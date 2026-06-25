from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.schemas.user_schema import UserCreate
from app.utils.security import hash_password, verify_password, create_access_token
from datetime import timedelta

import logging
import traceback

logger = logging.getLogger("app.services.auth_service")

def register_user(db: Session, user_in: UserCreate) -> User:
    """Register a new user inside the portal database."""
    logger.info(f"[DEBUG] register_user called for email={user_in.email}")
    
    # 1. Check if user already exists in User table
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        logger.warning(f"[DEBUG] Unique check failed: user with email {user_in.email} already exists in User table.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists"
        )
        
    # 2. Check if user already exists in Employee table to avoid unique constraint violation
    from app.models.employee import Employee
    existing_emp = db.query(Employee).filter(Employee.email == user_in.email).first()
    if existing_emp:
        logger.warning(f"[DEBUG] Unique check failed: employee with email {user_in.email} already exists in Employee table.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An employee profile with this email already exists in the system"
        )
        
    # 3. Create the User record
    hashed_pwd = hash_password(user_in.password)
    db_user = User(
        email=user_in.email,
        hashed_password=hashed_pwd,
        role="Admin",  # Registering a new workspace always creates an Admin!
        is_active=user_in.is_active
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"[DEBUG] User table record successfully created for {db_user.email}")
    except Exception as db_err:
        db.rollback()
        logger.error(f"[DEBUG] Failed to commit User record: {str(db_err)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database error creating user account: {str(db_err)}"
        )
    
    # 4. Create company, department, and employee records if names are provided
    full_name = getattr(user_in, "full_name", None)
    company_name = getattr(user_in, "company_name", None)
    if full_name or company_name:
        from app.models.company import Company
        from app.models.department import Department
        
        # Create or find company
        comp_name = company_name if company_name else "Phintra Enterprise"
        company = db.query(Company).filter(Company.company_name == comp_name).first()
        if not company:
            try:
                company = Company(
                    company_name=comp_name,
                    company_email=user_in.email,
                    company_address="Default Corporate HQ",
                    admin_id=db_user.id
                )
                db.add(company)
                db.commit()
                db.refresh(company)
                logger.info(f"[DEBUG] Created default company '{comp_name}' for new user")
            except Exception as comp_err:
                db.rollback()
                logger.error(f"[DEBUG] Failed to create custom company: {str(comp_err)}")
                # Fallback to get first company or seed new one
                company = db.query(Company).first()
                
        # Create default department operations for this company
        dept_name = "Security Operations"
        dept = db.query(Department).filter(Department.name == dept_name, Department.company_id == company.id).first() if company else None
        if not dept:
            try:
                dept = Department(
                    name=dept_name,
                    description=f"Default operations department for {comp_name}",
                    company_id=company.id if company else None
                )
                db.add(dept)
                db.commit()
                db.refresh(dept)
                logger.info(f"[DEBUG] Created default department '{dept_name}' for company '{comp_name}'")
            except Exception as dept_err:
                db.rollback()
                logger.error(f"[DEBUG] Failed to create custom department: {str(dept_err)}")
                dept = db.query(Department).filter(Department.name == "Security Operations").first()
                if not dept:
                    dept = Department(name="Security Operations", description="Default department")
                    db.add(dept)
                    db.commit()
                    db.refresh(dept)
                    
        if full_name:
            parts = full_name.strip().split(" ")
            first_name = parts[0]
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        else:
            first_name = "Admin"
            last_name = ""
            
        emp = db.query(Employee).filter(Employee.email == user_in.email).first()
        if not emp:
            try:
                emp = Employee(
                    name=full_name or f"{first_name} {last_name}".strip(),
                    first_name=first_name,
                    last_name=last_name,
                    email=user_in.email,
                    department_id=dept.id,
                    company_id=company.id if company else None,
                    risk_score=0.0,
                    status="Low Risk",
                    admin_id=db_user.id,
                    created_by=db_user.id,
                    is_active=True
                )
                db.add(emp)
                db.commit()
                logger.info(f"[DEBUG] Created admin employee record for {user_in.email}")
            except Exception as emp_err:
                db.rollback()
                logger.error(f"[DEBUG] Failed to create admin employee record: {str(emp_err)}")
                # We raise this to make sure we don't end up in an inconsistent state where User exists but Employee creation failed silent
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to initialize administrator employee profile: {str(emp_err)}"
                )
                
    return db_user

def authenticate_user(db: Session, email: str, password: str) -> str:
    """Authenticate portal user credentials and return a signed JWT access token."""
    # 1. First try User table (Admins/Managers)
    user = db.query(User).filter(User.email == email).first()
    if user:
        if not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is inactive"
            )
        return create_access_token(data={"sub": user.email, "role": user.role})
        
    # 2. Try Employee table
    from app.models.employee import Employee
    emp = db.query(Employee).filter(Employee.email == email).first()
    if emp:
        if not emp.password_hash or not verify_password(password, emp.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not emp.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee account is inactive"
            )
        return create_access_token(data={
            "sub": emp.email,
            "role": "Employee",
            "employee_id": str(emp.id)
        })
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
