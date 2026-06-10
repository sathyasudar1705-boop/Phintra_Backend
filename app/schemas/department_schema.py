from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class DepartmentBase(BaseModel):
    name: str
    description: Optional[str] = None
    manager_id: Optional[UUID] = None
    risk_score: Optional[int] = 0
    training_completion: Optional[int] = 0
    company_id: Optional[UUID] = None

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[UUID] = None
    risk_score: Optional[int] = None
    training_completion: Optional[int] = None
    company_id: Optional[UUID] = None

class DepartmentResponse(DepartmentBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Extended response to include employee counts or custom stats
class DepartmentDetailResponse(DepartmentResponse):
    employee_count: int = 0
    avg_risk_score: float = 0.0
