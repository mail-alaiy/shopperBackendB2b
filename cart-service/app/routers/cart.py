from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Dict, Optional
import redis
import json
from app.auth import get_current_user
from app.schemas import CartItem, CartResponse

router = APIRouter(prefix="/cart")

# Redis connection
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

def get_cart_key(user_id: str) -> str:
    return f"cart:{user_id}"

@router.get("", response_model=CartResponse)
async def get_cart(user_id: str = Depends(get_current_user)):
    """Get the contents of a user's cart"""
    cart_key = get_cart_key(user_id)
    cart_data = redis_client.hgetall(cart_key)
    
    if not cart_data:
        return {"items": {}}
    
    return {"items": cart_data}

@router.post("/items/{product_id}")
async def add_to_cart(
    product_id: str,
    quantity: int,
    user_id: str = Depends(get_current_user)
):
    """Add an item to the cart or update its quantity"""
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")
    
    cart_key = get_cart_key(user_id)
    current_quantity = redis_client.hget(cart_key, product_id)
    
    if current_quantity:
        new_quantity = int(current_quantity) + quantity
    else:
        new_quantity = quantity
    
    redis_client.hset(cart_key, product_id, str(new_quantity))
    return {"message": "Item added to cart", "quantity": new_quantity}

@router.put("/items/{product_id}")
async def update_cart_item(
    product_id: str,
    quantity: int,
    user_id: str = Depends(get_current_user)
):
    """Update the quantity of an item in the cart"""
    if quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be negative")
    
    cart_key = get_cart_key(user_id)
    if quantity == 0:
        redis_client.hdel(cart_key, product_id)
        return {"message": "Item removed from cart"}
    
    redis_client.hset(cart_key, product_id, str(quantity))
    return {"message": "Cart updated", "quantity": quantity}

@router.delete("/items/{product_id}")
async def remove_from_cart(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """Remove an item from the cart"""
    cart_key = get_cart_key(user_id)
    if redis_client.hdel(cart_key, product_id):
        return {"message": "Item removed from cart"}
    raise HTTPException(status_code=404, detail="Item not found in cart")

@router.delete("")
async def clear_cart(user_id: str = Depends(get_current_user)):
    """Clear all items from the cart"""
    cart_key = get_cart_key(user_id)
    redis_client.delete(cart_key)
    return {"message": "Cart cleared"} 