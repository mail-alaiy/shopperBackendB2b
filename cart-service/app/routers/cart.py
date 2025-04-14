from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Dict, Optional, List
import redis
import json
from dotenv import load_dotenv
from app.schemas import CartResponse, CartItemDetails, ProductSource, AddCartItemRequest
from pydantic import BaseModel
import os

load_dotenv()
router = APIRouter()

# Redis connection

REDIS_HOST = os.getenv("REDIS_HOST")
print(REDIS_HOST)
redis_client = redis.Redis(host="redis-62ad01f163fa3b2a.elb.ap-southeast-2.amazonaws.com", port=6379, db=0, decode_responses=True)

def get_cart_key(user_id: str) -> str:
    return f"cart:{user_id}"

@router.get("/debug")
async def debug_headers(request: Request):
    print(dict(request.headers))
    return dict(request.headers)

@router.get("/", response_model=CartResponse)
async def get_cart(x_user_id: str = Header(...)):
    """Get the contents of a user's cart"""
    cart_key = get_cart_key(x_user_id)
    cart_data_raw = redis_client.hgetall(cart_key)
    
    cart_items = {}
    if cart_data_raw:
        for product_id, item_json in cart_data_raw.items():
            try:
                item_data = json.loads(item_json)
                # Validate data against the Pydantic model
                cart_items[product_id] = CartItemDetails(**item_data)
            except (json.JSONDecodeError, TypeError, KeyError):
                # Handle cases where data in Redis is corrupted or not in the expected format
                # Optionally log this error
                continue # Skip corrupted item

    return CartResponse(items=cart_items)

@router.post("/items/{product_id}")
async def add_to_cart(
    product_id: str,
    item_data: AddCartItemRequest,
    x_user_id: str = Header(...)
):
    """Add an item to the cart or update its quantity if source matches."""
    cart_key = get_cart_key(x_user_id)
    print(REDIS_HOST)
    
    # Check if item already exists
    existing_item_json = redis_client.hget(cart_key, product_id)
    
    if existing_item_json:
        try:
            existing_item = CartItemDetails(**json.loads(existing_item_json))
            # Only update quantity if the source matches the existing item's source
            if existing_item.source == item_data.source:
                new_quantity = existing_item.quantity + item_data.quantity
                updated_item_data = CartItemDetails(quantity=new_quantity, source=item_data.source)
            else:
                # If source differs, overwrite the existing item (or handle as per specific business logic)
                # Current logic: Overwrite with new item data
                updated_item_data = CartItemDetails(quantity=item_data.quantity, source=item_data.source)
                
        except (json.JSONDecodeError, TypeError, KeyError):
            # Handle corrupted data - overwrite with new item
             updated_item_data = CartItemDetails(quantity=item_data.quantity, source=item_data.source)
    else:
        # Item does not exist, add new item
        updated_item_data = CartItemDetails(quantity=item_data.quantity, source=item_data.source)

    # Store as JSON string
    redis_client.hset(cart_key, product_id, updated_item_data.model_dump_json())
    
    return {"message": "Item added/updated in cart", "product_id": product_id, "details": updated_item_data}

# Define request model for PATCH
class CartItemUpdateRequest(BaseModel):
    quantity: Optional[int] = None
    source: Optional[str] = None  # Use the appropriate type based on your ProductSource enum

@router.patch("/items/{product_id}")
async def update_cart_item(
    product_id: str,
    update_data: CartItemUpdateRequest,
    x_user_id: str = Header(...)
):
    """Partially update an item in the cart (quantity and/or source)."""
    cart_key = get_cart_key(x_user_id)
    existing_item_json = redis_client.hget(cart_key, product_id)

    if not existing_item_json:
        raise HTTPException(status_code=404, detail="Item not found in cart")

    try:
        existing_item = CartItemDetails(**json.loads(existing_item_json))
    except (json.JSONDecodeError, TypeError, KeyError):
        raise HTTPException(status_code=500, detail="Error reading cart item data")

    # Handle quantity update
    if update_data.quantity is not None:
        if update_data.quantity < 0:
            raise HTTPException(status_code=400, detail="Quantity cannot be negative")
        
        if update_data.quantity == 0:
            redis_client.hdel(cart_key, product_id)
            return {"message": "Item removed from cart"}
        
        existing_item.quantity = update_data.quantity
    
    # Handle source update if provided
    if update_data.source is not None:
        try:
            # Validate source value against enum (if using enum)
            # ProductSource(update_data.source)  # Uncomment if using enum validation
            existing_item.source = update_data.source
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Invalid source value. Must be one of: Ex-china, Ex-india custom, doorstep delivery"
            )
    
    # Update the item in Redis
    redis_client.hset(cart_key, product_id, existing_item.model_dump_json())
    
    return {
        "message": "Cart item updated",
        "product_id": product_id,
        "details": existing_item
    }

@router.delete("/items/{product_id}")
async def remove_from_cart(
    product_id: str,
    x_user_id: str = Header(...)
):
    """Remove an item from the cart"""
    cart_key = get_cart_key(x_user_id)
    if redis_client.hdel(cart_key, product_id):
        return {"message": "Item removed from cart"}
    raise HTTPException(status_code=404, detail="Item not found in cart")

@router.delete("/")
async def clear_cart(x_user_id: str = Header(...)):
    """Clear all items from the cart"""
    cart_key = get_cart_key(x_user_id)
    redis_client.delete(cart_key)
    return {"message": "Cart cleared"} 