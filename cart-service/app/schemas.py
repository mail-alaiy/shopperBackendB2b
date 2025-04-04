from pydantic import BaseModel
from typing import Dict

class CartItem(BaseModel):
    product_id: str
    quantity: int

class CartResponse(BaseModel):
    items: Dict[str, str]  # product_id: quantity 