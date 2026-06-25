import uuid
from sqlalchemy import Column, String, DateTime, func, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    manager_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    risk_score = Column(Integer, default=0, nullable=False)
    training_completion = Column(Integer, default=0, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("Company", back_populates="departments")
    employees = relationship("Employee", back_populates="department", cascade="all, delete-orphan", foreign_keys="[Employee.department_id]")
    manager = relationship("Employee", foreign_keys=[manager_id], lazy="joined")
    security_scores = relationship("SecurityScore", back_populates="department", cascade="all, delete-orphan")
