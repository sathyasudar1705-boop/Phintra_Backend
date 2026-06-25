import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func, JSON

class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    module_id = Column(UUID(as_uuid=True), ForeignKey("training_modules.id", ondelete="CASCADE"), nullable=False)
    verification_code = Column(String, unique=True, nullable=False, index=True)
    issued_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee", back_populates="certificates")
    module = relationship("TrainingModule", back_populates="certificates")


class Reward(Base):
    __tablename__ = "rewards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    xp_amount = Column(Integer, nullable=False, default=100)
    description = Column(String, nullable=False)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())

    employee = relationship("Employee", back_populates="rewards")
