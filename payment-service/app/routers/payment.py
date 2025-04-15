from fastapi import APIRouter, Depends, HTTPException, Header, Request
import requests
from app.helpers import payment_utils
import json
from app.models import Payment
from datetime import datetime
import random
import base64
import traceback

router = APIRouter()

@router.get("/pay/{order_id}")
async def initiate_payment_for_order(
    order_id: str,
    x_user_id: str = Header(...),
    authorization: str = Header(...)
):
    try:
        print(f"[LOG] Initiating payment for order_id: {order_id}, user_id: {x_user_id}")

        # Step 1: Fetch required data
        print("[LOG] Fetching order details...")
        order_data = payment_utils.fetch_order_details(order_id, authorization)
        print(f"[LOG] Order data received: {order_data}")

        print("[LOG] Fetching user details...")
        user_data = payment_utils.fetch_user_details(authorization)
        print(f"[LOG] User data received: {user_data}")
        
        # Step 2: Validate order and extract payment details
        if order_data.get("merchantId") != x_user_id:
            print("[ERROR] Order does not belong to the user.")
            raise HTTPException(status_code=403, detail="Forbidden: Order does not belong to user.")
            
        if not (order_data.get("pStatus") == "UP" or order_data.get("pStatus") == "PU"):
            print(f"[ERROR] Invalid payment status: {order_data.get('pStatus')}")
            raise HTTPException(status_code=400, detail=f"Invalid payment status: {order_data.get('pStatus')}")

        total_amount = order_data.get("total_amount")
        if not total_amount or total_amount <= 0:
            print("[ERROR] Invalid total amount in order details.")
            raise HTTPException(status_code=400, detail="Invalid total amount in order details.")

        # Step 3: Determine contact details for payment
        phone_number_for_payment = user_data.get("mobile_number") or order_data.get("shippingPhoneNumber")
        user_email = user_data.get("email")
        
        if not phone_number_for_payment or not user_email:
            print("[ERROR] Missing phone number or email for payment.")
            raise HTTPException(
                status_code=400, 
                detail="Missing contact details for payment (phone or email)."
            )

        # Step 4: Initiate payment and return URL
        print("[LOG] Initiating PhonePe payment request...")
        phonepe_response = payment_utils.phonepePaymentURL(
            amount=total_amount,
            order_id=order_id,
            user_id=x_user_id,
            phone_number=phone_number_for_payment,
            email=user_email
        )
        
        data = phonepe_response.json()
        print(f"[LOG] PhonePe response received: {data}")

        payment_url = data.get("data", {}).get("instrumentResponse", {}).get("redirectInfo", {}).get("url")

        if data.get("success") and payment_url:
            merchant_transaction_id = data.get("data", {}).get("merchantTransactionId")
            print(f"[LOG] Preparing to save payment with transaction ID: {merchant_transaction_id}")

            # Step 5: Store payment record using MongoEngine
            try:
                payment = Payment(
                    merchantTransactionId=merchant_transaction_id,
                    userId=x_user_id,
                    amount=float(total_amount),
                    orderId=order_id,
                    status="PENDING"
                )
                payment.save()  # Synchronous save
                print("[LOG] Payment saved successfully.")
            except Exception as save_error:
                print("[ERROR] Failed to save payment to MongoDB:")
                print(traceback.format_exc())
                raise HTTPException(status_code=500, detail="Failed to save payment record.")

            return {"paymentUrl": payment_url}
        else:
            print("[ERROR] Invalid response from payment gateway.")
            raise HTTPException(status_code=502, detail="Invalid response from payment gateway.")

    except requests.exceptions.RequestException as e:
        service_name = ("Order Service" if payment_utils.ORDER_SERVICE_URL in str(e.request.url)
                     else "User Service" if payment_utils.USER_SERVICE_URL in str(e.request.url)
                     else "Payment Gateway")
        
        error_detail = f"Failed to connect to {service_name}"
        if getattr(e, "response", None):
            error_detail = f"{service_name} error: {e.response.status_code} - {e.response.text}"
        print(f"[ERROR] {error_detail}")
        raise HTTPException(status_code=502, detail=error_detail)

    except HTTPException as http_exc:
        print(f"[ERROR] HTTPException: {http_exc.detail}")
        raise

    except Exception as e:
        print("[ERROR] Unexpected internal server error:")
        print(traceback.format_exc())
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
        
        if "response" in webhook_data:
            encoded_response = webhook_data["response"]
            decoded_bytes = base64.b64decode(encoded_response)
            decoded_json = json.loads(decoded_bytes.decode('utf-8'))
            
            print(f"Decoded PhonePe response: {decoded_json}")
            
            if decoded_json.get("success") and decoded_json.get("data"):
                payment_data = decoded_json["data"]
                merchant_transaction_id = payment_data.get("merchantTransactionId")
                transaction_id = payment_data.get("transactionId")
                amount = payment_data.get("amount")
                payment_state = payment_data.get("state")
                response_code = payment_data.get("responseCode")
                
                # Build paymentDetails structure
                payment_details = json.dumps([{
                    "paymentMode": payment_data.get("paymentInstrument", {}).get("type", "UPI"),
                    "transactionId": transaction_id,
                    "timestamp": int(datetime.utcnow().timestamp() * 1000),
                    "amount": int(amount),
                    "state": payment_state,
                    "splitInstruments": [{
                        "amount": int(amount),
                        "rail": {
                            "type": "PG",
                            "transactionId": transaction_id,
                            "serviceTransactionId": f"PG{datetime.utcnow().strftime('%y%m%d%H%M%S')}{random.randint(1000000000, 9999999999)}"
                        },
                        "instrument": payment_data.get("paymentInstrument", {})
                    }]
                }])

                # Update the Payment document using MongoEngine
                paymentStatus = "SUCCESS" if payment_state == "COMPLETED" else "PENDING"
                payment = Payment.objects(merchantTransactionId=merchant_transaction_id).first()
                if payment:
                    payment.status = paymentStatus
                    payment.paymentDetails = payment_details
                    payment.save()

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