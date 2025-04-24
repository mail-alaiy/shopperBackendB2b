from fastapi import APIRouter, HTTPException, Depends, Header, Request, Query, status
from typing import Dict, Optional, List
import redis
import json
from dotenv import load_dotenv
from app.schemas import CartResponse, CartItemDetails, ProductSource, AddCartItemRequest
from pydantic import BaseModel, ValidationError
import os

load_dotenv()
router = APIRouter(prefix="/cart")

# Redis connection

REDIS_HOST = os.getenv("REDIS_HOST")
print(REDIS_HOST)
redis_client = redis.Redis(host="redis-62ad01f163fa3b2a.elb.ap-southeast-2.amazonaws.com", port=6379, db=0, decode_responses=True)

def extract_user_id_from_event(request: Request) -> str:
    event = request.scope.get("aws.event", {})
    authorizer = event.get("requestContext", {}).get("authorizer", {})

    user_id = authorizer.get("userId")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing userId in requestContext.authorizer")

    return user_id

def get_cart_key(user_id: str) -> str:
    return f"cart:{user_id}"

# Helper function to find a variant in a list
def find_variant_index(items: List[Dict], variant_index: Optional[int]) -> int:
    for i, item in enumerate(items):
        if item.get("variantIndex") == variant_index:
            return i
    return -1

# Helper function to parse cart items from Redis
def parse_cart_items(items_json_list: List[str]) -> List[CartItemDetails]:
    parsed_items = []
    for item_json in items_json_list:
        try:
            item_data = json.loads(item_json)
            parsed_items.append(CartItemDetails(**item_data))
        except (json.JSONDecodeError, TypeError, KeyError, ValidationError):
            # Optionally log corrupted item data
            continue # Skip corrupted items
    return parsed_items

@router.get("/debug")
async def debug_headers(request: Request):
    print(dict(request.headers))
    return dict(request.headers)

@router.get("/", response_model=CartResponse)
async def get_cart(x_user_id: str = Depends(extract_user_id_from_event)):
    """Get the contents of a user's cart, supporting variants."""
    cart_key = get_cart_key(x_user_id)
    cart_data_raw = redis_client.hgetall(cart_key)

    cart_items_response: Dict[str, List[CartItemDetails]] = {}
    if cart_data_raw:
        for product_id, items_json in cart_data_raw.items():
            try:
                # items_json is expected to be a JSON string of a list of variant dicts
                items_list = json.loads(items_json)
                if not isinstance(items_list, list):
                    # Handle potential data corruption if it's not a list
                    # Optionally log this error
                    continue # Skip this product_id

                product_variants = []
                for item_data in items_list:
                     # Validate each item against the Pydantic model
                    try:
                        product_variants.append(CartItemDetails(**item_data))
                    except (TypeError, KeyError, ValidationError):
                        # Handle cases where individual variant data is corrupted
                        # Optionally log this error
                        continue # Skip corrupted variant item
                
                if product_variants: # Only add if there are valid variants
                    cart_items_response[product_id] = product_variants

            except (json.JSONDecodeError, TypeError):
                # Handle cases where the entire value for a product_id is corrupted
                # Optionally log this error
                continue # Skip corrupted product_id entry

    return CartResponse(items=cart_items_response)

@router.post("/items/{product_id}")
async def add_to_cart(
    product_id: str,
    item_data: AddCartItemRequest,
    x_user_id: str = Depends(extract_user_id_from_event)
):
    """Add an item/variant to the cart or update quantity if source and variantIndex match."""
    cart_key = get_cart_key(x_user_id)
    
    # Get current list of variants for the product, if any
    existing_items_json = redis_client.hget(cart_key, product_id)
    variants: List[Dict] = [] # Store as list of dicts before saving
    if existing_items_json:
        try:
            variants = json.loads(existing_items_json)
            if not isinstance(variants, list): # Ensure it's a list
                variants = [] # Reset if data is corrupt
        except json.JSONDecodeError:
            variants = [] # Reset if data is corrupt
            
    # Find if the specific variant (matched by variantIndex) already exists
    variant_match_index = find_variant_index(variants, item_data.variantIndex)

    updated = False
    if variant_match_index != -1:
        # Variant exists, check source
        existing_variant = variants[variant_match_index]
        if existing_variant.get("source") == item_data.source.value:
            # Source matches, update quantity
            existing_variant["quantity"] += item_data.quantity
            updated = True
        else:
            # Source differs, overwrite the variant (as per original logic)
            variants[variant_match_index] = {
                "quantity": item_data.quantity,
                "source": item_data.source.value,
                "variantIndex": item_data.variantIndex
            }
            updated = True
    
    if not updated:
         # Variant doesn't exist or source differed, add as new variant
        variants.append({
            "quantity": item_data.quantity,
            "source": item_data.source.value,
            "variantIndex": item_data.variantIndex
        })

    # Store the updated list of variants as a JSON string
    redis_client.hset(cart_key, product_id, json.dumps(variants))

    # Prepare response detail matching the added/updated item structure
    response_detail = next((v for i, v in enumerate(variants) if find_variant_index([v], item_data.variantIndex) != -1), None)

    return {"message": "Item added/updated in cart", "product_id": product_id, "details": response_detail}

# Define request model for PATCH including variantIndex
class CartItemUpdateRequest(BaseModel):
    quantity: Optional[int] = None
    source: Optional[ProductSource] = None # Use the enum type
    variantIndex: Optional[int] = None # Add variantIndex to specify which item

@router.patch("/items/{product_id}")
async def update_cart_item(
    product_id: str,
    update_data: CartItemUpdateRequest,
    x_user_id: str = Depends(extract_user_id_from_event)
):
    """Partially update a specific item variant in the cart."""
    cart_key = get_cart_key(x_user_id)
    existing_items_json = redis_client.hget(cart_key, product_id)

    if not existing_items_json:
        raise HTTPException(status_code=404, detail="Product not found in cart")

    try:
        variants = json.loads(existing_items_json)
        if not isinstance(variants, list):
             raise HTTPException(status_code=500, detail="Cart item data is corrupted")
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=500, detail="Error reading cart item data")

    # Find the specific variant to update
    variant_match_index = find_variant_index(variants, update_data.variantIndex)

    if variant_match_index == -1:
         raise HTTPException(status_code=404, detail="Specific variant not found in cart")

    target_variant = variants[variant_match_index]

    # Handle quantity update
    if update_data.quantity is not None:
        if update_data.quantity < 0:
            raise HTTPException(status_code=400, detail="Quantity cannot be negative")
        
        if update_data.quantity == 0:
            # Remove this specific variant from the list
            variants.pop(variant_match_index)
            # If list is now empty, remove the product from the cart hash
            if not variants:
                redis_client.hdel(cart_key, product_id)
                return {"message": "Item variant removed from cart"}
            else:
                # Update redis with the modified list
                redis_client.hset(cart_key, product_id, json.dumps(variants))
                return {"message": "Item variant removed from cart"}
        
        target_variant["quantity"] = update_data.quantity
    
    # Handle source update
    if update_data.source is not None:
        # No need for explicit validation here as Pydantic handles it via ProductSource enum
        target_variant["source"] = update_data.source.value
            
    # Update the item list in Redis
    redis_client.hset(cart_key, product_id, json.dumps(variants))
    
    # Return the updated variant details
    updated_variant_details = CartItemDetails(**target_variant) # Convert back for response

    return {
        "message": "Cart item variant updated",
        "product_id": product_id,
        "details": updated_variant_details
    }

@router.delete("/items/{product_id}")
async def remove_from_cart(
    product_id: str,
    x_user_id: str = Depends(extract_user_id_from_event),
    variantIndex: Optional[int] = Query(None) # Add variantIndex as optional query param
):
    """Remove a specific item variant from the cart."""
    cart_key = get_cart_key(x_user_id)
    existing_items_json = redis_client.hget(cart_key, product_id)

    if not existing_items_json:
        raise HTTPException(status_code=404, detail="Product not found in cart")

    try:
        variants = json.loads(existing_items_json)
        if not isinstance(variants, list):
            raise HTTPException(status_code=500, detail="Cart item data is corrupted")
    except (json.JSONDecodeError, TypeError):
         raise HTTPException(status_code=500, detail="Error reading cart item data")

    # Find the specific variant to delete
    variant_match_index = find_variant_index(variants, variantIndex)

    if variant_match_index == -1:
         raise HTTPException(status_code=404, detail="Specific variant not found in cart")

    # Remove the variant from the list
    variants.pop(variant_match_index)

    # If the list is now empty, remove the product key from the cart hash
    if not variants:
        redis_client.hdel(cart_key, product_id)
    else:
        # Otherwise, update the list in Redis
        redis_client.hset(cart_key, product_id, json.dumps(variants))

    return {"message": "Item variant removed from cart"}

@router.delete("/")
async def clear_cart(x_user_id: str = Depends(extract_user_id_from_event)):
    """Clear all items from the cart"""
    cart_key = get_cart_key(x_user_id)
    redis_client.delete(cart_key) # This remains the same, deletes the whole user cart hash
    return {"message": "Cart cleared"} 