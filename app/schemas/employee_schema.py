from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID

class EmployeeBase(BaseModel):
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr
    department_id: UUID
    company_id: Optional[UUID] = None
    risk_score: float = 0.0
    status: str = "Low Risk"
    is_active: Optional[bool] = True
    role: str = "employee"

class EmployeeCreate(EmployeeBase):
    password: Optional[str] = None
    created_by: Optional[UUID] = None

class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    department_id: Optional[UUID] = None
    company_id: Optional[UUID] = None
    risk_score: Optional[float] = None
    status: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None

class EmployeeResponse(EmployeeBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class EmployeeDetailResponse(EmployeeResponse):
    department_name: Optional[str] = None
    is_active: bool = True
    has_password: bool = False
    total_points: Optional[int] = 0
    click_count: Optional[int] = 0
    report_count: Optional[int] = 0
    training_progress: Optional[str] = "0.0%"
