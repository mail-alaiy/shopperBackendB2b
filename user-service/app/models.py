from sqlalchemy import Column, String, DateTime, Enum as SQLAlchemyEnum, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timedelta, timezone
from .database import Base
import enum
import secrets

# Define Role Enum
class RoleEnum(str, enum.Enum):
    customer = "customer"
    admin = "admin"

class BusinessTypeEnum(str, enum.Enum):
    manufacturer = "Manufacturer"
    distributor = "Distributor"
    retailer = "Retailer"
    reseller = "Reseller"

class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Business Information
    company_name = Column(String, nullable=False)
    business_type = Column(SQLAlchemyEnum(BusinessTypeEnum), nullable=False)
    business_street = Column(String, nullable=False)
    business_city = Column(String, nullable=False)
    business_state = Column(String, nullable=False)
    business_country = Column(String, nullable=False)

    # Contact Details
    full_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)

    # Tax & Compliance
    gst_number = Column(String, nullable=False)

    # Account Security & Verification
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)

    # Use the RoleEnum for the role field
    role = Column(SQLAlchemyEnum(RoleEnum), default=RoleEnum.customer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationship to verification tokens (can be one-to-many if multiple attempts are allowed before cleanup)
    verification_tokens = relationship("VerificationToken", back_populates="user", cascade="all, delete-orphan")

# New table for verification tokens
class VerificationToken(Base):
    __tablename__ = 'verification_tokens'

    token = Column(String, primary_key=True, unique=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="verification_tokens")

    def __init__(self, user_id: uuid.UUID, expiry_minutes: int = 60):
        self.token = secrets.token_urlsafe(32)
        self.user_id = user_id
        self.expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
