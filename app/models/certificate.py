import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func, JSON

class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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


class ReportedEmail(Base):
    __tablename__ = "reported_emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=True)
    employee_name = Column(String, nullable=True)
    employee_email = Column(String, nullable=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    campaign_name = Column(String, nullable=True)
    email_subject = Column(String, nullable=False)
    email_sender = Column(String, nullable=False)
    email_body = Column(String, nullable=True)
    report_reason = Column(String, nullable=True)
    report_status = Column(String, default="Pending", nullable=False) # Pending, Safe, Suspicious, Closed
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    report_source = Column(String, default="direct", nullable=True)
    message_id = Column(String, nullable=True)
    thread_id = Column(String, nullable=True)
    reported_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Keep compatibility with existing code
    reported_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    subject = Column(String, nullable=True)
    sender = Column(String, nullable=True)
    email_date = Column(DateTime(timezone=True), nullable=True)
    risk_score = Column(Integer, default=0, nullable=True)
    risk_level = Column(String, default="Low", nullable=True)
    status = Column(String, default="Pending", nullable=True)
    analysis_results = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    employee = relationship("Employee", back_populates="reported_emails")
