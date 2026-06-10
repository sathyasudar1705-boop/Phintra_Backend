import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class TrainingModule(Base):
    __tablename__ = "training_modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    duration_minutes = Column(Integer, nullable=False, default=10)
    xp_reward = Column(Integer, nullable=False, default=100)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    assignments = relationship("TrainingAssignment", back_populates="module", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="module", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="module", cascade="all, delete-orphan")


class TrainingAssignment(Base):
    __tablename__ = "training_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    module_id = Column(UUID(as_uuid=True), ForeignKey("training_modules.id", ondelete="CASCADE"), nullable=False)
    progress = Column(Integer, default=0, nullable=False) # 0 to 100
    completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    employee = relationship("Employee", back_populates="training_assignments")
    module = relationship("TrainingModule", back_populates="assignments")
