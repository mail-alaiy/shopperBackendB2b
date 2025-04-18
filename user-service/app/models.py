from sqlalchemy import Column, String, DateTime, Enum as SQLAlchemyEnum
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from .database import Base
import enum

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

    # Account Security
    password_hash = Column(String, nullable=False)

    # Use the RoleEnum for the role field
    role = Column(SQLAlchemyEnum(RoleEnum), default=RoleEnum.customer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
