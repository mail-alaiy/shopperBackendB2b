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

# Helper function to find a variant in a list by index AND source
def find_variant_index_and_source(items: List[Dict], variant_index: Optional[int], source: ProductSource) -> int:
    for i, item in enumerate(items):
        # Check both variantIndex and source match
        if item.get("variantIndex") == variant_index and item.get("source") == source.value:
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
    """Add an item/variant to the cart. If item with same variantIndex and source exists, update quantity. Otherwise, add as a new entry."""
    cart_key = get_cart_key(x_user_id)
    
    existing_items_json = redis_client.hget(cart_key, product_id)
    variants: List[Dict] = [] 
    if existing_items_json:
        try:
            variants = json.loads(existing_items_json)
            if not isinstance(variants, list): 
                variants = [] 
        except json.JSONDecodeError:
            variants = [] 
            
    # Find if the specific variant (matched by variantIndex AND source) already exists
    # Use the new helper function
    exact_match_index = find_variant_index_and_source(variants, item_data.variantIndex, item_data.source)

    if exact_match_index != -1:
        # Exact match found (same product, variantIndex, and source), update quantity
        variants[exact_match_index]["quantity"] += item_data.quantity
    else:
         # No exact match found, add as a new variant entry
        variants.append({
            "quantity": item_data.quantity,
            "source": item_data.source.value,
            "variantIndex": item_data.variantIndex
        })

    redis_client.hset(cart_key, product_id, json.dumps(variants))

    # Find the specific item added/updated for the response
    response_detail = None
    if exact_match_index != -1:
        response_detail = variants[exact_match_index]
    else:
        # Find the newly added item (it will be the last one with matching variantIndex and source)
         for variant in reversed(variants):
             if variant.get("variantIndex") == item_data.variantIndex and variant.get("source") == item_data.source.value:
                 response_detail = variant
                 break

    return {"message": "Item added/updated in cart", "product_id": product_id, "details": response_detail}

# Define request model for PATCH - Only quantity can be updated
class CartItemUpdateRequest(BaseModel):
    quantity: int # Required field for the update

@router.patch("/items/{product_id}")
async def update_cart_item(
    product_id: str,
    update_data: CartItemUpdateRequest, # Body now only contains quantity
    variantIndex: int = Query(..., description="The variantIndex of the item to update"),
    source: ProductSource = Query(..., description="The source of the item to update"),
    x_user_id: str = Depends(extract_user_id_from_event)
):
    """
    Update the quantity of a specific item variant in the cart.
    The item is identified by product_id, variantIndex, and source via query parameters.
    The request body must contain the new 'quantity'.
    """
    cart_key = get_cart_key(x_user_id)
    existing_items_json = redis_client.hget(cart_key, product_id)

    if not existing_items_json:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in cart")

    try:
        variants = json.loads(existing_items_json)
        if not isinstance(variants, list):
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Cart item data is corrupted")
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error reading cart item data")

    # Find the specific variant to update using required variantIndex and source from query params
    variant_match_index = find_variant_index_and_source(variants, variantIndex, source)

    if variant_match_index == -1:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Specific variant with index {variantIndex} and source '{source.value}' not found in cart for this product")

    target_variant = variants[variant_match_index]

    # --- Handle Quantity Update ---
    new_quantity = update_data.quantity
    if new_quantity < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity cannot be negative")

    if new_quantity == 0:
        # Remove this specific variant from the list
        variants.pop(variant_match_index)
        message = f"Item variant (index: {variantIndex}, source: {source.value}) removed via zero quantity update"
        # If list is now empty, remove the product from the cart hash
        if not variants:
            redis_client.hdel(cart_key, product_id)
            # Return immediately after deleting the hash key
            return {"message": message}
        else:
            # Update redis with the modified list (item removed)
            redis_client.hset(cart_key, product_id, json.dumps(variants))
            # Return immediately after updating the list
            return {"message": message}

    # Update the quantity for the target variant
    target_variant["quantity"] = new_quantity

    # --- Source update logic is removed ---

    # Update the item list in Redis with the new quantity
    redis_client.hset(cart_key, product_id, json.dumps(variants))

    # Return the updated variant details
    updated_variant_details = CartItemDetails(**target_variant)

    return {
        "message": "Cart item quantity updated",
        "product_id": product_id,
        "details": updated_variant_details
    }

@router.delete("/items/{product_id}")
async def remove_from_cart(
    product_id: str,
    x_user_id: str = Depends(extract_user_id_from_event),
    variantIndex: int = Query(..., description="The variantIndex of the item to remove."), # Now required
    source: ProductSource = Query(..., description="The source of the item to remove.") # Now required
):
    """
    Remove a specific item variant from the cart.
    Requires both 'variantIndex' and 'source' query parameters to identify the exact item.
    """
    cart_key = get_cart_key(x_user_id)
    existing_items_json = redis_client.hget(cart_key, product_id)

    if not existing_items_json:
        # Use standard 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found in cart")

    try:
        variants = json.loads(existing_items_json)
        if not isinstance(variants, list):
            # Use standard 500 for server-side data issues
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Cart item data is corrupted")
    except (json.JSONDecodeError, TypeError):
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error reading cart item data")

    # Find the specific variant to delete using the required index and source
    variant_match_index = find_variant_index_and_source(variants, variantIndex, source)

    # Check if the specific variant was found
    if variant_match_index == -1:
         # Use standard 404
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Specific variant with index {variantIndex} and source '{source.value}' not found in cart for this product")

    # Remove the variant from the list
    deleted_item_details = variants.pop(variant_match_index)

    # If the list is now empty, remove the product key from the cart hash
    if not variants:
        redis_client.hdel(cart_key, product_id)
    else:
        # Otherwise, update the list in Redis
        redis_client.hset(cart_key, product_id, json.dumps(variants))

    # Return a confirmation message, optionally including details of the removed item
    return {
        "message": "Item variant removed from cart",
        "removed_item": CartItemDetails(**deleted_item_details).model_dump()
    }

@router.delete("/")
async def clear_cart(x_user_id: str = Depends(extract_user_id_from_event)):
    """Clear all items from the cart"""
    cart_key = get_cart_key(x_user_id)
    redis_client.delete(cart_key) # This remains the same, deletes the whole user cart hash
    return {"message": "Cart cleared"} 