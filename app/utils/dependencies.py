from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Dependency to retrieve currently authenticated user from database via JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    email: str = payload.get("sub")
    emp_id: str = payload.get("employee_id")
    if email is None:
        raise credentials_exception
        
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        from app.models.employee import Employee
        emp = None
        if emp_id:
            emp = db.query(Employee).filter(Employee.id == emp_id).first()
        else:
            emp = db.query(Employee).filter(Employee.email == email).first()
            
        if emp is None:
            raise credentials_exception
        if not emp.is_active:
            raise HTTPException(status_code=400, detail="Inactive employee")
            
        class MockUser:
            def __init__(self, id, email, role, is_active, admin_id):
                self.id = id
                self.email = email
                self.role = role
                self.is_active = is_active
                self.admin_id = admin_id
        return MockUser(id=emp.id, email=emp.email, role="Employee", is_active=emp.is_active, admin_id=emp.admin_id)
        
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user

class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{user.role}' does not have permission to access this resource"
            )
        return user

# Helper definitions for route injection
require_admin = RoleChecker(["Admin"])
require_manager = RoleChecker(["Admin", "Manager"])
require_employee = RoleChecker(["Admin", "Manager", "Employee"])
