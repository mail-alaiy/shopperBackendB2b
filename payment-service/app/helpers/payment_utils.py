import hashlib
import base64
import uuid
import json
import requests
import os
import app.constants as constants # Use relative import for constants
from fastapi import HTTPException
from . import email_helper # Import the new email helper

# Load Order Service URL once from environment
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL")
if not ORDER_SERVICE_URL:
    raise ValueError("ORDER_SERVICE_URL environment variable not set in payment_utils.")

# Load User Service URL once from environment
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
if not USER_SERVICE_URL:
    raise ValueError("USER_SERVICE_URL environment variable not set in payment_utils.")

def create_sha256_string(input_string):
    """Generates a SHA256 hash string."""
    sha256_hash = hashlib.sha256(input_string.encode())
    encoded_string = sha256_hash.hexdigest()
    return encoded_string

def string_to_base64(input_string):
    """Encodes a string to Base64."""
    encoded_string = base64.b64encode(input_string.encode())
    return encoded_string.decode()

def phonepePaymentURL(amount: int, order_id: str, user_id: str, phone_number: str, email: str):
    """Constructs and sends the payment initiation request to PhonePe."""
    merchantTransactionID = f"MT-{order_id[:8]}-{str(uuid.uuid4())[:8]}"
    merchantUserId = f"User_{user_id}"
    mobileNumber = phone_number
    
    payload = {
        "amount": amount * 100,
        "merchantId": constants.merchant_id,
        "merchantTransactionId": merchantTransactionID,
        "merchantUserId": merchantUserId,
        "redirectUrl": constants.redirect_url,
        "redirectMode": "REDIRECT",
        "callbackUrl": constants.webhook_url,
        "merchantOrderId": order_id,
        "mobileNumber": mobileNumber,
        "email": email,
        "message": f"Payment for Order {order_id}",
        "paymentInstrument": {"type": "PAY_PAGE"}
    }
    print(f"PhonePe Request Payload: {payload}")
    json_data = json.dumps(payload)
    base64_request = string_to_base64(json_data)

    # Construct X-VERIFY header
    verify_string = base64_request + "/pg/v1/pay" + constants.salt_key
    finalXHeader = create_sha256_string(verify_string) + "###" + constants.salt_index

    req = {"request": base64_request}
    finalHeader = {
        "Content-Type": "application/json",
        "X-VERIFY": finalXHeader
    }

    print(f"PhonePe Request Payload: {payload}")
    response = requests.post(constants.payment_url, headers=finalHeader, json=req)
    print(f"PhonePe Response Status: {response.status_code}")
    return response

def checkStatus(merchantTransactionID: str):
    """Checks the status of a transaction with PhonePe."""
    endpoint_path = f"{constants.status_endpoint}/{constants.merchant_id}/{merchantTransactionID}"
    url = constants.base_url + endpoint_path

    # Construct X-VERIFY header
    verify_string = endpoint_path + constants.salt_key
    finalXHeader = create_sha256_string(verify_string) + "###" + constants.salt_index

    headers = {
        "Content-Type": "application/json",
        "X-VERIFY": finalXHeader,
        "X-MERCHANT-ID": constants.merchant_id
    }

    print(f"Checking PhonePe status for MTID: {merchantTransactionID}")
    response = requests.get(url, headers=headers)
    print(f"PhonePe Status Check Response Status: {response.status_code}")

    if response.status_code == 200:
        return response.json()
    else:
        return f"Something went wrong - Status: {response.status_code}, Body: {response.text}"

def fetch_order_details(order_id: str, authorization: str):
    """Fetches order details from the order service."""
    order_service_url = f"{ORDER_SERVICE_URL}/order/{order_id}"
    headers = {"Authorization": authorization}
    print(f"Fetching order details from: {order_service_url}")
    
    try:
        response = requests.get(order_service_url, headers=headers)
        print(f"Order service response status: {response.status_code}")
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Order not found.")
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Unauthorized to fetch order details.")
        
        response.raise_for_status()
        order_data = response.json()
        
        if "payload" not in order_data or not order_data["payload"]:
            raise HTTPException(status_code=404, detail="Order details payload not found.")
            
        return order_data["payload"]
    except requests.exceptions.RequestException as e:
        print(f"Order service request failed: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to Order Service: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error fetching order details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching order details.")

def fetch_user_details(authorization: str):
    """Fetches user details from the user service."""
    user_service_url = f"{USER_SERVICE_URL}/me"
    headers = {"Authorization": authorization}
    print(f"Fetching user details from: {user_service_url}")
    
    try:
        response = requests.get(user_service_url, headers=headers)
        print(f"User service response status: {response.status_code}")
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="User not found.")
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Unauthorized to fetch user details.")
            
        response.raise_for_status()
        user_data = response.json()
        
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found or empty response.")
            
        return user_data
    except requests.exceptions.RequestException as e:
        print(f"User service request failed: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to User Service: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error fetching user details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while fetching user details.")

def send_payment_confirmation_email(user_id: str, amount: float, order_id: str):
    """Gets user email and triggers sending of payment confirmation email."""
    print(f"Attempting to send payment confirmation for order {order_id} to user {user_id}")

    # 1. Get User Email
    recipient_email = email_helper.get_user_email(user_id)

    if not recipient_email:
        print(f"Could not retrieve email for user {user_id}. Skipping payment confirmation email.")
        return

    # 2. Construct Email Content
    # Ensure amount is formatted nicely (e.g., two decimal places)
    formatted_amount = "{:.2f}".format(amount / 100.0) # Assuming amount is in paise
    subject = f"Payment Confirmation for Order {order_id}"
    html_body = f"""
        <p>Dear User,</p>
        <p>Your payment of ₹{formatted_amount} for order <strong>{order_id}</strong> has been successfully processed.</p>
        <p>Thank you for your purchase!</p>
        <p>You can view your order details in your account.</p>
    """

    

    if success:
        print(f"Payment confirmation email request triggered successfully for user {user_id}, order {order_id}")
    else:
        print(f"Failed to trigger payment confirmation email request for user {user_id}, order {order_id}") 