from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class BusinessTypeEnum(str, Enum):
    manufacturer = "Manufacturer"
    distributor = "Distributor"
    retailer = "Retailer"
    reseller = "Reseller"


class UserBase(BaseModel):
    # Business Info
    company_name: str
    business_type: BusinessTypeEnum
    business_street: str
    business_city: str
    business_state: str
    business_country: str

    # Contact
    full_name: str
    phone_number: str
    email: EmailStr

    # Tax
    gst_number: str

    class Config:
        orm_mode = True


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    company_name: Optional[str] = None
    business_type: Optional[BusinessTypeEnum] = None
    business_street: Optional[str] = None
    business_city: Optional[str] = None
    business_state: Optional[str] = None
    business_country: Optional[str] = None

    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    gst_number: Optional[str] = None

    class Config:
        orm_mode = True


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str


class UserOut(BaseModel):
    id: UUID
    company_name: str
    business_type: BusinessTypeEnum
    business_street: str
    business_city: str
    business_state: str
    business_country: str

    full_name: str
    phone_number: str
    email: EmailStr
    gst_number: str
    role: str
    created_at: datetime

    class Config:
        orm_mode = True
