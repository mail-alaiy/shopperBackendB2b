from pydantic import BaseModel, EmailStr
from typing import Optional

class CreateOrderRequest(BaseModel):
    currency: str
    shippingPhoneNumber: str
    shippingAddress1: str
    shippingAddress2: Optional[str] = None
    shippingAddress3: Optional[str] = None
    recipientName: str
    shippingCity: str
    shippingState: str
    shippingPostalCode: str
    shippingCountry: str
    source: int
