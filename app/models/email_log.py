import uuid
from sqlalchemy import Column, String, DateTime, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class EmailLog(Base):
    __tablename__ = "email_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    campaign_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    template_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    recipient_email = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    status = Column(String, nullable=False) # Sent, Failed
    error_message = Column(String, nullable=True)
    employee_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())


class ThreatFeed(Base):
    __tablename__ = "threat_feed"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    source = Column(String, nullable=True)
    severity = Column(String, default="Low", nullable=False) # Low, Medium, High, Critical
    published_at = Column(DateTime(timezone=True), server_default=func.now())
