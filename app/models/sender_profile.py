import uuid
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class SenderProfile(Base):
    __tablename__ = "sender_profiles"

    profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain = Column(String, nullable=False)
    email_address = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    company_name = Column(String, nullable=True)
    department = Column(String, nullable=True)
