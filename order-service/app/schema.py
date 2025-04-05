from pydantic import BaseModel, EmailStr
from typing import Optional

class CreateOrderRequest(BaseModel):
    currency: str
    shippingPhoneNumber: str
    shippingAddress1: str
    shippingAddress2: str
    shippingAddress3: str
    recipientName: str
    shippingCity: str
    shippingState: str
    shippingPostalCode: str
    shippingCountry: str
    source: int
