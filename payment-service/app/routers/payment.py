from fastapi import APIRouter, Depends, HTTPException, Header, Request
import requests
from ..auth import get_current_user
from ..helpers import payment_utils
import json

router = APIRouter()

@router.post("/pay/{order_id}")
async def initiate_payment_for_order(
    order_id: str,
    user_id: str = Depends(get_current_user),
    authorization: str = Header(...)
):
    try:
        # Step 1a: Fetch order details
        order_data = payment_utils.fetch_order_details(order_id, authorization)
        print(f"Order Data: {order_data}") # Log fetched order data

        # Step 1b: Fetch user details
        user_data = payment_utils.fetch_user_details(authorization)
        print(f"User Data: {user_data}") # Log fetched user data

        # Step 2: Validate Order Ownership and Status
        if order_data.get("merchantId") != user_id:
            print(f"Order ownership mismatch: Order MerchantId={order_data.get('merchantId')}, Auth UserId={user_id}")
            raise HTTPException(status_code=403, detail="Forbidden: Order does not belong to user.")
        if order_data.get("pStatus") != "UP":
            raise HTTPException(status_code=400, detail=f"Order payment status not UP (Current: {order_data.get('pStatus')}).")
        total_amount = order_data.get("total_amount")
        if total_amount is None or total_amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid total amount in order details.")

        # Step 3: Extract Phone Numbers
        shipping_phone = order_data.get("shippingPhoneNumber")
        # Extract user mobile number, default to None if fetch failed or number not present
        user_mobile = user_data.get("mobile_number") if user_data else None 
        print(f"Shipping Phone: {shipping_phone}, User Mobile: {user_mobile}")
        
        # Decide which number to use for PhonePe (e.g., prioritize user number)
        # Using shipping phone as fallback if user mobile is not available
        phone_number_for_payment = shipping_phone or user_mobile 
        
        # Ensure a valid phone number is available for the PhonePe request
        if not phone_number_for_payment:
             print("Error: Could not determine a valid phone number for payment from user or order details.")
             raise HTTPException(status_code=400, detail="Could not determine phone number for payment.") # UNCOMMENTED
        
        print(f"Using phone number for payment: {phone_number_for_payment}")

        # Extract email from user data
        user_email = user_data.get("email") if user_data else None
        
        # Ensure email is available
        if not user_email:
            print("Error: Could not determine a valid email for payment from user details.")
            raise HTTPException(status_code=400, detail="Could not determine email for payment.")
        
        print(f"Using email for payment: {user_email}")
        print(f"Order validated for user {user_id}. Initiating payment for amount: {total_amount}")

        # Step 4: Initiate PhonePe Payment using helper function, passing the email
        phonepe_response = payment_utils.phonepePaymentURL(
            amount=total_amount, 
            order_id=order_id, 
            user_id=user_id, 
            phone_number=phone_number_for_payment,
            email=user_email  # Pass the email from user data
        )
        phonepe_response.raise_for_status()

        data = phonepe_response.json()
        if data.get("success") and data.get("data", {}).get("instrumentResponse", {}).get("redirectInfo", {}).get("url"):
            return data["data"]["instrumentResponse"]["redirectInfo"]["url"]
        else:
            print(f"Unexpected PhonePe response structure: {data}")
            raise HTTPException(status_code=502, detail="Bad response from payment gateway.")

    except requests.exceptions.RequestException as e:
        # Updated error check to include USER_SERVICE_URL
        service_name = "Order Service" if payment_utils.ORDER_SERVICE_URL in str(e.request.url) \
                       else ("User Service" if payment_utils.USER_SERVICE_URL in str(e.request.url) else "Payment Gateway")
        print(f"HTTP Request failed for {service_name}: {e}")
        error_detail = f"Failed to connect to {service_name}."
        if e.response is not None:
            error_detail = f"{service_name} error: {e.response.status_code} - {e.response.text}"
        raise HTTPException(status_code=502, detail=error_detail)
    except HTTPException as e:
        raise e # Re-raise validation/auth errors
    except Exception as e:
        print(f"Unexpected error in /pay endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")

# New endpoint for PhonePe webhook notifications
@router.post("/webhook/phonepe")
async def phonepe_webhook(request: Request):
    """
    Handles incoming webhook notifications from PhonePe.
    Logs the received data and returns a success response.
    """
    try:
        webhook_data = await request.json()
        print(f"Received PhonePe webhook data: {webhook_data}")
        
        # Extract and decode the base64-encoded response
        if "response" in webhook_data:
            import base64
            import json
            
            # Decode the base64 response
            encoded_response = webhook_data["response"]
            decoded_bytes = base64.b64decode(encoded_response)
            decoded_json = json.loads(decoded_bytes.decode('utf-8'))
            
            print(f"Decoded PhonePe response: {decoded_json}")
            
            # Extract important payment information
            if decoded_json.get("success") and decoded_json.get("data"):
                payment_data = decoded_json["data"]
                merchant_transaction_id = payment_data.get("merchantTransactionId")
                transaction_id = payment_data.get("transactionId")
                amount = payment_data.get("amount")
                payment_state = payment_data.get("state")
                response_code = payment_data.get("responseCode")
                
                print(f"Payment {transaction_id} for order {merchant_transaction_id} is {payment_state}")
                print(f"Amount: {amount}, Response code: {response_code}")
                
                # TODO: Update your order status based on payment status
                # Example:
                # if payment_state == "COMPLETED" and response_code == "SUCCESS":
                #     update_order_payment_status(merchant_transaction_id, "PAID")
                # elif payment_state == "FAILED":
                #     update_order_payment_status(merchant_transaction_id, "FAILED")
                
                return {
                    "status": "success", 
                    "message": "Payment processed",
                    "payment_status": payment_state,
                    "transaction_id": transaction_id
                }
            
        return {"status": "success", "message": "Webhook received"}
    except json.JSONDecodeError:
        print("Error decoding JSON from PhonePe webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        print(f"Error processing PhonePe webhook: {e}")
        # Avoid leaking internal error details in production
        raise HTTPException(status_code=500, detail="Internal server error processing webhook")

# If you need the status check endpoint later:
# @router.get("/status/{merchantTransactionID}")
# async def check_payment_status(merchantTransactionID: str):
#     try:
#         status_response = payment_utils.checkStatus(merchantTransactionID)
#         if isinstance(status_response, str) and status_response.startswith("Something went wrong"):
#             raise HTTPException(status_code=502, detail=status_response)
#         return status_response
#     except Exception as e:
#         print(f"Error checking status: {e}")
#         raise HTTPException(status_code=500, detail="Error checking payment status.") 