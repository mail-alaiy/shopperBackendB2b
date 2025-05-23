from fastapi import APIRouter, Depends, HTTPException, Header, Path, Body, status, Request
from mongoengine.errors import ValidationError as MongoValidationError
from bson import json_util
import json
from bson.objectid import ObjectId
import requests
from jose import jwt, JWTError
from app.helpers import email_helper
from app.models import Order, OrderDetails
from datetime import datetime
import os
from app.schema import CreateOrderRequest
router = APIRouter(prefix="/orders")
CART_URL = os.getenv("CART_URL")
PRODUCT_URL = os.getenv("PRODUCT_URL")
USER_URL = os.getenv("USER_URL")
ORDER_UPDATE_TOKEN = os.getenv("ACCESS_TOKEN_SECRET_UPDATE")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

def extract_user_id_from_event(request: Request) -> str:
    event = request.scope.get("aws.event", {})
    authorizer = event.get("requestContext", {}).get("authorizer", {})

    user_id = authorizer.get("userId")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing userId in requestContext.authorizer")

    return user_id

@router.get("/")
async def get_orders(x_user_id: str = Depends(extract_user_id_from_event)):
    try:
        # MongoEngine query using the Order model
        orders = Order.objects(merchantId=x_user_id)

        if not orders:
            return {"message": "No orders found", "payload": []}

        # Convert each Order object to a MongoDB document dict
        serialized_orders = json.loads(json_util.dumps([order.to_mongo() for order in orders]))

        return {
            "message": "Successfully retrieved orders",
            "payload": serialized_orders
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/")
async def delete_orders(x_user_id: str = Depends(extract_user_id_from_event)):
    try:
        deleted_count = Order.objects(merchantId=x_user_id).delete()
        
        if deleted_count == 0:
            return {"message": "No orders found to delete", "deleted_count": 0}
        
        return {
            "message": "Successfully deleted orders",
            "deleted_count": deleted_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete orders: {str(e)}")
    
@router.post("/")
async def create_order(
    order_data: CreateOrderRequest,
    x_user_id: str = Depends(extract_user_id_from_event),
    authorization: str = Header(None)
):
    try:
        headers = {"Authorization": authorization}
        cart_response = requests.get(f"{CART_URL}/", headers=headers)

        if cart_response.status_code != 200:
            raise HTTPException(status_code=cart_response.status_code, detail="Failed to fetch cart")

        cart_json = cart_response.json()
        cart_items = cart_json.get("items", {})
        if not cart_items:
            raise HTTPException(status_code=400, detail="Cart is empty")
        
        user_response = requests.get(f"{USER_URL}/me", headers=headers)
        if user_response.status_code != 200:
            raise HTTPException(status_code=user_response.status_code, detail="Failed to fetch cart")
        
        user_json = user_response.json()
        user_gst_number = user_json.get("gst_number", "")
        product_ids = list(cart_items.keys())

        # Step 2: Fetch product details
        products_response = requests.post(
            f"{PRODUCT_URL}/multiple-products",
            json={"product_ids": product_ids}
        )

        if products_response.status_code != 200:
            raise HTTPException(status_code=products_response.status_code, detail="Failed to fetch product details")

        products_json = products_response.json()
        products = products_json.get("payload", [])
        if not products:
            raise HTTPException(status_code=404, detail="No product details found")

        # Step 3: Prepare OrderDetails list using MongoEngine
        total_price = 0
        order_details_list = []
        for prod in products:
            prod_id = prod.get("_id")
            if isinstance(prod_id, dict):
                prod_id = prod_id.get("$oid", "")
            elif isinstance(prod_id, str):
                prod_id = prod_id
            else:
                continue

            sku_value = prod.get("skus", [])
            gst_percentage = prod.get("gst", "0")
            sku_retrieved = str(sku_value[0]) if isinstance(sku_value, list) and sku_value else ""

            # 🛠️ FIX: Properly handle cart_items[prod_id] as a list
            cart_item_list = cart_items.get(prod_id, [])
            cart_item = cart_item_list[0] if isinstance(cart_item_list, list) and cart_item_list else {}

            quantity = max(1, int(cart_item.get("quantity", 1)))
            source = cart_item.get("source")
            sp = prod.get("sp", 0)
            price_to_use = sp

            if 'variable_pricing' in prod and prod['variable_pricing']:
                for price_tier in prod['variable_pricing']:
                    for range_str, price in price_tier.items():
                        if range_str.startswith('>'):
                            min_qty = int(range_str[1:])
                            if quantity >= min_qty:
                                price_to_use = price
                                break
                        else:
                            range_parts = range_str.split('-')
                            min_qty = int(range_parts[0])
                            max_qty = int(range_parts[1])
                            if min_qty <= quantity <= max_qty:
                                price_to_use = price
                                break
            flag_gst = False
            cgst = 0
            sgst = 0
            igst = 0
            total_gst = price_to_use/(float(gst_percentage)+1)
            
            if user_gst_number.startswith("06"):
                cgst = total_gst/2
                sgst = total_gst/2
            else:
                igst = total_gst
            total_price += quantity * price_to_use
            order_details = OrderDetails(
                sku=sku_retrieved,
                sellerSku=sku_retrieved,
                quantity=quantity,
                quantityShipped=quantity,
                consumerPrice=price_to_use,
                title=prod.get("name", ""),
                source=source,
                cgst = cgst,
                sgst = sgst,
                igst = igst
            )
            order_details_list.append(order_details)

        order = Order(
            currency=order_data.currency,
            shippingPhoneNumber=order_data.shippingPhoneNumber,
            shippingAddress1=order_data.shippingAddress1,
            shippingAddress2=order_data.shippingAddress2,
            shippingAddress3=order_data.shippingAddress3,
            pStatus="PU",
            source=order_data.source,
            shipDate=None,
            shippingMethod="Bluedart brands 500 g Surface",
            merchantId=x_user_id,
            mkpOrderId=f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            orderDetails=order_details_list,
            recipientName=order_data.recipientName,
            shippingCity=order_data.shippingCity,
            shippingState=order_data.shippingState,
            shippingPostalCode=order_data.shippingPostalCode,
            shippingCountry=order_data.shippingCountry,
            total_amount=total_price
        )

        order.save()
        return {
            "message": "Order created successfully",
            "payload": json.loads(json_util.dumps(order.to_mongo()))
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/order/{order_id}")
async def get_order_by_id(order_id: str, x_user_id: str = Depends(extract_user_id_from_event)):
    try:
        if not ObjectId.is_valid(order_id):
            raise HTTPException(status_code=400, detail="Invalid order ID")
        order = Order.objects(id=ObjectId(order_id), merchantId=x_user_id).first()

        if not order:
            return {"message": "Order not found or not authorized", "payload": {}}

        serialized_order = json.loads(json_util.dumps(order.to_mongo()))

        return {
            "message": "Successfully retrieved order",
            "payload": serialized_order
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/order/{order_id}")
async def update_order_by_id(order_id: str, update_data: dict = Body(...), x_user_id: str = Depends(extract_user_id_from_event)):
    try:
        if not ObjectId.is_valid(order_id):
            raise HTTPException(status_code=400, detail="Invalid order ID")
        order = Order.objects(id=order_id, merchantId=x_user_id).first()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found or not authorized")
        for key, value in update_data.items():
            if hasattr(order, key):
                setattr(order, key, value)

        order.save()

        return {
            "message": "Order successfully updated",
            "order_id": order_id,
            "updated_fields": update_data
        }

    except MongoValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.delete("/order/{order_id}")
async def delete_order_by_id(order_id: str, x_user_id: str = Depends(extract_user_id_from_event)):
    try:
        if not ObjectId.is_valid(order_id):
            raise HTTPException(status_code=400, detail="Invalid order ID")

        order = Order.objects(id=order_id, merchantId=x_user_id).first()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found or not authorized")

        order.delete()

        return {
            "message": "Order successfully deleted",
            "order_id": order_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/payment-status")
async def update_payment_status(
    body: dict = Body(...)
):
    try:
        token = body.get("token")

        if not token:
            raise HTTPException(status_code=400, detail="Missing token in request body")

        # Decode token
        try:
            decoded = jwt.decode(token, ORDER_UPDATE_TOKEN, algorithms=[JWT_ALGORITHM])
        except JWTError as e:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        order_id = decoded.get("order_id")
        email_id = decoded.get("user_email")

        if not order_id or not ObjectId.is_valid(order_id):
            raise HTTPException(status_code=400, detail="Invalid or missing order ID in token")

        # Look up order
        order = Order.objects(id=order_id).first()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found or not owned by the user")

        # Update payment status
        order.pStatus = "PD"
        order.paidDate = datetime.utcnow()
        order.save()

        return {
            "message": "Payment status updated successfully",
            "payload": json.loads(json_util.dumps(order.to_mongo()))
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/admin/orders/{user_id}")
async def admin_get_orders(user_id: str):
    try:
        # MongoEngine query using the Order model
        orders = Order.objects(merchantId=user_id)

        if not orders:
            return {"message": "No orders found", "payload": []}

        # Convert each Order object to a MongoDB document dict
        serialized_orders = json.loads(json_util.dumps([order.to_mongo() for order in orders]))

        return {
            "message": "Successfully retrieved orders",
            "payload": serialized_orders
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/order/{order_id}")
async def admin_get_order_by_id(order_id: str = Path(..., description="MongoDB Order ID to fetch")):
    try:
        if not ObjectId.is_valid(order_id):
            raise HTTPException(status_code=400, detail="Invalid order ID format")

        # Query directly by ID without checking merchantId for admin access
        order = Order.objects(id=ObjectId(order_id)).first()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        # Serialize the order to a dictionary suitable for JSON response
        serialized_order = json.loads(json_util.dumps(order.to_mongo()))

        return {
            "message": "Successfully retrieved order",
            "payload": serialized_order
        }

    except HTTPException:
        # Re-raise HTTPException to preserve status code and detail
        raise
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")