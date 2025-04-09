from pydantic import BaseModel, Field
from typing import Dict
from enum import Enum

class ProductSource(str, Enum):
    ex_china = "Ex-china"
    ex_india_custom = "Ex-india custom"
    doorstep_delivery = "doorstep delivery"

class CartItemDetails(BaseModel):
    quantity: int
    source: ProductSource

class AddCartItemRequest(BaseModel):
    quantity: int = Field(..., gt=0) # Ensure quantity is positive
    source: ProductSource

class CartResponse(BaseModel):
    items: Dict[str, CartItemDetails] 