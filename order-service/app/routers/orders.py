from fastapi import APIRouter, Depends, HTTPException, Header, Path
from bson import json_util
import json
from app.auth import get_current_user
from bson.objectid import ObjectId
from bson import json_util
import json
import requests
import app.database
from app.auth import get_current_user
from app.models import Order, OrderDetails
from datetime import datetime
import os
from app.schema import CreateOrderRequest

router = APIRouter()
CART_URL = os.getenv("CART_URL")
PRODUCT_URL = os.getenv("PRODUCT_URL")

@router.get("/orders")
async def get_orders(user_id: str = Depends(get_current_user)):
    try:
        # MongoEngine query using the Order model
        print(f"👤 User ID: {user_id}")
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

    

@router.get("/orders/{order_id}")
async def get_order_by_id(order_id: str, user_id: str = Depends(get_current_user)):
    try:
        if not ObjectId.is_valid(order_id):
            raise HTTPException(status_code=400, detail="Invalid order ID")

        # Use MongoEngine's Order model to fetch the order
        order = Order.objects(id=ObjectId(order_id), merchantId=user_id).first()

        if not order:
            return {"message": "Order not found or not authorized", "payload": {}}

        serialized_order = json.loads(json_util.dumps(order.to_mongo()))

        return {
            "message": "Successfully retrieved order",
            "payload": serialized_order
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/order")
async def create_order(
    order_data: CreateOrderRequest,
    user_id: str = Depends(get_current_user),
    authorization: str = Header(None)
):
    try:
        headers = {"Authorization": authorization}
        print(f"\n🔐 Authorization: {authorization}")
        print(f"👤 User ID: {user_id}")
        print(f"📦 Calling Cart Service: {CART_URL}/cart")

        # Step 1: Get Cart Items
        cart_response = requests.get(f"{CART_URL}/cart", headers=headers)
        print(f"🛒 Cart response status: {cart_response.status_code}")

        if cart_response.status_code != 200:
            raise HTTPException(status_code=cart_response.status_code, detail="Failed to fetch cart")

        cart_json = cart_response.json()
        print(f"🛒 Cart JSON: {cart_json}")

        cart_items = cart_json.get("items", {})
        if not cart_items:
            raise HTTPException(status_code=400, detail="Cart is empty")

        product_ids = list(cart_items.keys())
        print(f"🛒 Product IDs in Cart: {product_ids}")

        # Step 2: Fetch product details
        products_response = requests.post(
            f"{PRODUCT_URL}/multiple-products",
            json={"product_ids": product_ids}
        )
        print(f"📦 Product response status: {products_response.status_code}")

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
                print(f"⚠️ Unexpected _id format: {prod_id}")
                continue

            print(f"🆔 Resolved Product ID: {prod_id}")

            sku_value = prod.get("skus", [])
            sku_retrieved = str(sku_value[0]) if isinstance(sku_value, list) and sku_value else ""

            cart_item = cart_items.get(prod_id, {})
            quantity = max(1, int(cart_item.get("quantity", 1)))
            source = cart_item.get("source")
            print(f"📦 SKU: {sku_retrieved} | Quantity: {quantity}")
            sp = prod.get("sp", 0)
            total_price += quantity*sp
            order_details = OrderDetails(
                sku=sku_retrieved,
                sellerSku=sku_retrieved,
                quantity=quantity,
                quantityShipped=quantity,
                consumerPrice=sp,
                title=prod.get("name", ""),
                source = source
            )
            order_details_list.append(order_details)

        # Step 4: Create and save Order
        order = Order(
            currency=order_data.currency,
            shippingPhoneNumber=order_data.shippingPhoneNumber,
            shippingAddress1=order_data.shippingAddress1,
            shippingAddress2=order_data.shippingAddress2,
            shippingAddress3=order_data.shippingAddress3,
            pStatus="UP",
            source=order_data.source,
            shipDate=None,
            shippingMethod="Bluedart brands 500 g Surface",
            merchantId=user_id,
            mkpOrderId=f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            orderDetails=order_details_list,
            recipientName=order_data.recipientName,
            shippingCity=order_data.shippingCity,
            shippingState=order_data.shippingState,
            shippingPostalCode=order_data.shippingPostalCode,
            shippingCountry=order_data.shippingCountry,
            total_amount = total_price
        )

        order.save()

        print(f"\n✅ Order saved successfully for user: {user_id}")
        return {
            "message": "Order created successfully",
            "payload": json.loads(json_util.dumps(order.to_mongo()))
        }

    except Exception as e:
        print(f"❌ Error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/orders/{order_id}")
async def delete_order_by_id(
    order_id: str,
    user_id: str = Depends(get_current_user)
):
    try:
        if not ObjectId.is_valid(order_id):
            raise HTTPException(status_code=400, detail="Invalid order ID")

        # Use MongoEngine to find the order
        order = Order.objects(id=order_id, merchantId=user_id).first()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found or not authorized")

        # Delete the order
        order.delete()

        return {
            "message": "Order successfully deleted",
            "order_id": order_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/payment-status/{order_id}")
async def update_payment_status(
    order_id: str = Path(..., description="MongoDB Order ID to mark as paid"),
    user_id: str = Depends(get_current_user),
    authorization: str = Header(None)
):
    try:
        if not ObjectId.is_valid(order_id):
            raise HTTPException(status_code=400, detail="Invalid order ID format")

        print(f"\n🔐 Authorization: {authorization}")
        print(f"👤 User ID: {user_id}")
        print(f"💰 Updating payment status for Order ID: {order_id}")

        order = Order.objects(id=order_id, merchantId=user_id).first()

        if not order:
            raise HTTPException(status_code=404, detail="Order not found or not owned by the user")

        order.pStatus = "PD"  # Paid
        order.paidDate = datetime.utcnow()
        order.save()

        print(f"✅ Payment status updated to PD for Order ID: {order_id}")

        return {
            "message": "Payment status updated successfully",
            "payload": json.loads(json_util.dumps(order.to_mongo()))
        }

    except Exception as e:
        print(f"❌ Error updating payment status: {e}")
        raise HTTPException(status_code=500, detail=str(e))