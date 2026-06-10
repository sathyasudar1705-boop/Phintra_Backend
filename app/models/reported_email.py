import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class ReportedEmail(Base):
    __tablename__ = "reported_emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id = Column(UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    employee_name = Column(String, nullable=False)
    employee_email = Column(String, nullable=False)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    campaign_name = Column(String, nullable=True)
    email_subject = Column(String, nullable=False)
    sender_email = Column(String, nullable=False)
    email_body = Column(Text, nullable=False)
    threat_score = Column(Integer, nullable=False)
    report_reason = Column(String, nullable=False)
    report_status = Column(String, nullable=False, default="Pending")
    reported_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    employee = relationship("Employee", back_populates="reported_emails")
    campaign = relationship("Campaign", back_populates="reported_emails")
    reviewer = relationship("User", backref="reviewed_reports")
