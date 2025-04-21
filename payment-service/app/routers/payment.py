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
    Updates payment status and triggers confirmation email on success.
    """
    decoded_json = None # Define outside try block
    merchant_transaction_id = None # Define outside try block

    try:
        webhook_data = await request.json()
        print(f"Received PhonePe webhook data: {webhook_data}")

        if "response" not in webhook_data:
             print("Webhook data missing 'response' field.")
             return {"status": "ignored", "message": "Webhook ignored, missing response field"}

        encoded_response = webhook_data["response"]
        decoded_bytes = base64.b64decode(encoded_response)
        decoded_json = json.loads(decoded_bytes.decode('utf-8'))

        print(f"Decoded PhonePe response: {decoded_json}")

        if not decoded_json.get("success") or not decoded_json.get("data"):
            print("Decoded response indicates failure or missing data.")
            return {"status": "ignored", "message": "Webhook ignored, unsuccessful or missing data"}

        payment_data = decoded_json["data"]
        merchant_transaction_id = payment_data.get("merchantTransactionId")
        transaction_id = payment_data.get("transactionId") # PhonePe's transaction ID
        amount = payment_data.get("amount") # Amount in paise
        payment_state = payment_data.get("state") # e.g., COMPLETED, FAILED
        response_code = payment_data.get("responseCode") # e.g., SUCCESS

        if not merchant_transaction_id:
            print("Merchant Transaction ID missing from webhook data.")
            # Cannot update our record without this ID
            return {"status": "error", "message": "Missing merchantTransactionId"}

        # Fetch the payment record from DB
        payment = Payment.objects(merchantTransactionId=merchant_transaction_id).first()
        if not payment:
            print(f"Payment record not found for MTID: {merchant_transaction_id}")
            # Cannot proceed without the payment record (which contains userId, orderId)
            return {"status": "error", "message": "Payment record not found"}

        # Build paymentDetails structure (optional, keep if useful)
        # ... (your existing paymentDetails logic) ...
        payment_details_json = json.dumps([{
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

        original_status = payment.status
        new_status = "UNKNOWN" # Default

        if payment_state == "COMPLETED" and response_code == "SUCCESS":
            new_status = "SUCCESS"
        elif payment_state == "FAILED":
            new_status = "FAILED"
        # Add more states if needed (PENDING, etc.)
        else:
            new_status = payment_state # Store the state if not explicitly success/failed

        # Update Payment Document
        payment.status = new_status
        payment.paymentDetails = payment_details_json # Update with latest details
        # Add phonepe's transaction ID if you want to store it
        # payment.providerTransactionId = transaction_id
        payment.save()
        print(f"Payment record {merchant_transaction_id} updated to status: {new_status}")

        # --- Send Confirmation Email on Success ---
        if new_status == "SUCCESS" and original_status != "SUCCESS": # Only send if status changed to SUCCESS
            try:
                # Pass necessary details: user ID, amount (in paise), order ID
                payment_utils.send_payment_confirmation_email(
                    user_id=payment.userId,
                    amount=float(amount), # Ensure amount is float/int
                    order_id=payment.orderId
                )
            except Exception as email_exc:
                # Log email sending errors but don't fail the webhook response
                print(f"Error during email sending trigger: {email_exc}")
                print(traceback.format_exc())
        # ------------------------------------------

        return {
            "status": "success",
            "message": f"Webhook processed for {merchant_transaction_id}. Status: {new_status}"
        }

    except json.JSONDecodeError:
        print("Error decoding JSON from PhonePe webhook")
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