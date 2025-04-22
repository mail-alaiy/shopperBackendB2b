from fastapi import APIRouter, Depends, HTTPException, Header, Request
import requests
from app.helpers import payment_utils, email_helper
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
    user_id_for_email = None # Store user ID for email sending

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
                transaction_id = payment_data.get("transactionId") # PhonePe's Txn ID
                amount = payment_data.get("amount") # Amount is in paise
                payment_state = payment_data.get("state")
                response_code = payment_data.get("responseCode") # e.g., SUCCESS, PAYMENT_ERROR

                print(f"[LOG] Merchant Txn ID: {merchant_transaction_id}, State: {payment_state}, Code: {response_code}")

                # Determine internal status based on PhonePe state/code
                # PAYMENT_SUCCESS is the primary indicator for successful transaction completion
                is_successful_payment = (payment_state == "COMPLETED" and response_code == "SUCCESS")
                payment_status = "SUCCESS" if is_successful_payment else "FAILED" if payment_state == "FAILED" else "PENDING" # Default to PENDING if unclear

                print(f"[LOG] Mapped internal payment status: {payment_status}")

                # Find the payment record in our DB
                payment = Payment.objects(merchantTransactionId=merchant_transaction_id).first()

                if payment:
                    print(f"[LOG] Found Payment record in DB for MTID: {merchant_transaction_id}. Current DB status: {payment.status}")
                    user_id_for_email = payment.userId # Store user ID before potentially changing status

                    # Update payment record only if status is changing or details need update
                    if payment.status != payment_status or not payment.paymentDetails:
                        payment.status = payment_status
                        # Construct payment details JSON (consider moving to a helper if complex)
                        payment_details_dict = {
                            "providerTransactionId": transaction_id,
                            "providerStatus": payment_state,
                            "responseCode": response_code,
                            "paymentInstrument": payment_data.get("paymentInstrument", {}),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        payment.paymentDetails = json.dumps(payment_details_dict)
                        payment.save()
                        print(f"[LOG] Payment record updated successfully to status: {payment_status}")
                    else:
                         print(f"[LOG] Payment status already '{payment.status}'. No DB update needed.")


                    # --- Order Update and Email Sending (only on first success) ---
                    if is_successful_payment and payment.status == "SUCCESS": # Check *our* determined SUCCESS status
                        print(f"[LOG] Processing successful payment actions for {merchant_transaction_id}")

                        # 1. Update Order Service (Assuming this should only happen once)
                        # Check if order update was already attempted/successful if needed
                        try:
                            payload = {"order_id": payment.orderId}
                            print(f"[LOG] Encoding JWT token for order update with payload: {payload}")
                            token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
                            print(f"[LOG] Sending PUT request to ORDER_UPDATE_URL: {ORDER_UPDATE_URL}")
                            response = requests.put(ORDER_UPDATE_URL, json={"token": token}, timeout=10) # Added timeout
                            response.raise_for_status()
                            print(f"[LOG] Order update request successful: {response.status_code}")
                        except jwt.JWTError as jwt_err:
                            print(f"[ERROR] JWT encoding failed for order update: {jwt_err}")
                            # Decide if this should block email or just log
                        except RequestException as put_error:
                            print(f"[ERROR] Failed to send PUT request to order update URL.")
                            print(f"[ERROR] Details: {put_error}")
                            # Log error, but proceed to email attempt
                            # Consider adding retry logic or background task for order update failures
                        except Exception as order_update_err:
                            print(f"[ERROR] Unexpected error during order update: {order_update_err}")
                            print(traceback.format_exc())


                        # 2. Send Confirmation Email
                        if user_id_for_email:
                            print(f"[LOG] Attempting to send confirmation email for user: {user_id_for_email}")
                            user_email = email_helper.get_user_email(user_id_for_email)
                            if user_email:
                                subject = f"Payment Confirmation for Order {payment.orderId}"
                                # Convert paise to rupees for display
                                amount_in_rupees = amount / 100.0
                                html_body = (
                                    f"<h1>Payment Successful!</h1>"
                                    f"<p>Thank you for your payment of ₹{amount_in_rupees:.2f} for order ID {payment.orderId}.</p>"
                                    f"<p>Your payment transaction ID is {merchant_transaction_id}.</p>"
                                    f"<p>Provider Transaction ID: {transaction_id}</p>"
                                )
                                success = email_helper.send_email_with_resend(user_email, subject, html_body)
                                if success:
                                    print(f"[LOG] Successfully sent payment confirmation email to {user_email}")
                                else:
                                    print(f"[ERROR] Failed to send payment confirmation email to {user_email}")
                            else:
                                print(f"[WARN] Could not find email for user {user_id_for_email}. Cannot send confirmation email.")
                        else:
                             print("[WARN] User ID not found in payment record. Cannot fetch email.")

                    # --- End Successful Payment Actions ---

                else:
                    print(f"[WARN] No payment record found for MerchantTransactionId: {merchant_transaction_id}. Cannot process webhook.")
                    # Return error to PhonePe if MTID is unknown? Or just log?
                    # For now, log and return success to avoid retries for unknown MTIDs.

                # Respond to PhonePe - Success indicates we received and processed (or attempted to process) the webhook
                # It doesn't necessarily mean the payment *was* successful from the user's perspective.
                return {"status": "success", "message": f"Webhook processed for {merchant_transaction_id}"}

            else:
                print("[ERROR] Webhook received but success flag is false or data is missing in decoded response.")
                raise HTTPException(status_code=400, detail="Invalid webhook data format or content")

        else:
            print("[ERROR] 'response' key not found in webhook payload.")
            raise HTTPException(status_code=400, detail="Invalid webhook payload structure")

    except json.JSONDecodeError:
        print("[ERROR] Error decoding JSON from PhonePe webhook.")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except base64.binascii.Error:
         print("[ERROR] Error decoding Base64 response from PhonePe webhook.")
         raise HTTPException(status_code=400, detail="Invalid Base64 encoding")
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions raised intentionally elsewhere (like auth errors from email_helper)
        raise http_exc
    except Exception as e:
        # Log detailed error, including decoded data if available
        error_details = f"Error processing PhonePe webhook: {e}"
        if decoded_json:
            error_details += f" | Decoded Data MTID: {decoded_json.get('data', {}).get('merchantTransactionId', 'N/A')}"
        elif merchant_transaction_id:
             error_details += f" | MTID: {merchant_transaction_id}"
        print(f"[CRITICAL] {error_details}")
        print(traceback.format_exc())
        # Return success to PhonePe to avoid retries for internal processing errors,
        # but log the failure clearly. Consider specific error responses if needed.
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