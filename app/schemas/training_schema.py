from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# Training Module Schemas
class TrainingModuleBase(BaseModel):
    title: str
    description: Optional[str] = None
    duration_minutes: int = 10
    xp_reward: int = 100

class TrainingModuleCreate(TrainingModuleBase):
    pass

class TrainingModuleUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    xp_reward: Optional[int] = None

class TrainingModuleResponse(TrainingModuleBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Training Assignment Schemas
class TrainingAssignmentBase(BaseModel):
    employee_id: UUID
    module_id: UUID
    progress: int = 0
    completed: bool = False
    completed_at: Optional[datetime] = None

class TrainingAssignmentCreate(TrainingAssignmentBase):
    pass

class TrainingAssignmentUpdate(BaseModel):
    progress: Optional[int] = None
    completed: Optional[bool] = None
    completed_at: Optional[datetime] = None

class TrainingAssignmentResponse(TrainingAssignmentBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TrainingAssignBulkRequest(BaseModel):
    employee_ids: List[UUID]
