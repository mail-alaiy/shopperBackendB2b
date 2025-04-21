from fastapi import APIRouter, Depends, HTTPException, Header, Request
import requests
from app.helpers import payment_utils
import json
from jose import jwt, JWTError
from app.models import Payment
from datetime import datetime
import random
import base64
import traceback
import os
from requests.exceptions import RequestException
from dotenv import load_dotenv
load_dotenv()
router = APIRouter()

SECRET_KEY = os.getenv("ACCESS_TOKEN_SECRET_UPDATE")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
ORDER_UPDATE_URL = os.getenv("ORDER_UPDATE_URL")

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
    Updates payment status and triggers confirmation email on success.
    """
    decoded_json = None # Define outside try block
    merchant_transaction_id = None # Define outside try block

    try:
        webhook_data = await request.json()
        print(f"[LOG] Received PhonePe webhook data: {webhook_data}")
        
        if "response" in webhook_data:
            encoded_response = webhook_data["response"]
            print("[LOG] Decoding base64 encoded response...")
            decoded_bytes = base64.b64decode(encoded_response)
            decoded_json = json.loads(decoded_bytes.decode('utf-8'))
            print(f"[LOG] Decoded PhonePe response JSON: {decoded_json}")
            
            if decoded_json.get("success") and decoded_json.get("data"):
                payment_data = decoded_json["data"]
                merchant_transaction_id = payment_data.get("merchantTransactionId")
                transaction_id = payment_data.get("transactionId")
                amount = payment_data.get("amount")
                payment_state = payment_data.get("state")
                response_code = payment_data.get("responseCode")

                print(f"[LOG] Merchant Txn ID: {merchant_transaction_id}, Txn ID: {transaction_id}, Amount: {amount}, State: {payment_state}")

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

                paymentStatus = "SUCCESS" if payment_state == "COMPLETED" else "PENDING"
                print(f"[LOG] Mapped internal payment status: {paymentStatus}")

                payment = Payment.objects(merchantTransactionId=merchant_transaction_id).first()
                if payment:
                    print(f"[LOG] Found Payment record in DB. Updating status and payment details.")
                    payment.status = paymentStatus
                    payment.paymentDetails = payment_details
                    payment.save()
                    print(f"[LOG] Payment record updated successfully.")

                    if paymentStatus == "SUCCESS":
                        try:
                            payload = {"order_id": payment.orderId}
                            print(f"[LOG] Encoding JWT token with payload: {payload}")
                            token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
                            print(f"[LOG] Encoded token: {token}")

                            print(f"[LOG] Sending PUT request to ORDER_UPDATE_URL: {ORDER_UPDATE_URL}")
                            response = requests.put(ORDER_UPDATE_URL, json={"token": token})
                            response.raise_for_status()
                            print(f"[LOG] Order update response: {response.status_code} - {response.text}")
                        except RequestException as put_error:
                            print(f"[ERROR] Failed to send PUT request to order update URL.")
                            print(f"[ERROR] Details: {put_error}")
                            raise HTTPException(status_code=502, detail="Failed to update order status")

                else:
                    print(f"[WARN] No payment record found for MerchantTransactionId: {merchant_transaction_id}")

        return {
            "status": "success",
            "message": f"Webhook processed for {merchant_transaction_id}. Status: {new_status}"
        }

    except json.JSONDecodeError:
        print("[ERROR] Error decoding JSON from PhonePe webhook.")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        # Log detailed error, including decoded data if available
        error_details = f"Error processing PhonePe webhook: {e}"
        if decoded_json:
            error_details += f" | Decoded Data MTID: {decoded_json.get('data', {}).get('merchantTransactionId', 'N/A')}"
        elif merchant_transaction_id:
             error_details += f" | MTID: {merchant_transaction_id}"
        print(error_details)
        print(traceback.format_exc())
        # Return success to PhonePe to avoid retries for processing errors,
        # but log the failure clearly. Consider specific error responses if needed.
        # raise HTTPException(status_code=500, detail="Internal server error processing webhook")
        return {"status": "error", "message": "Internal server error during webhook processing"}

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