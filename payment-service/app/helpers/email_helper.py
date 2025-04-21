import requests
import os
from fastapi import HTTPException
import traceback

# Load User Service URL once from environment
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
if not USER_SERVICE_URL:
    raise ValueError("USER_SERVICE_URL environment variable not set in email_helper.")

# Placeholder for internal authentication (e.g., an API key for user-service)
INTERNAL_AUTH_HEADER = {"X-Internal-API-Key": os.getenv("USER_SERVICE_INTERNAL_KEY", "default-secret-key")} # Replace with secure key management

def get_user_email(user_id: str) -> str | None:
    """Fetches user email from the User Service using user ID."""
    user_service_url = f"{USER_SERVICE_URL}/admin/user/{user_id}" # Use admin endpoint assuming internal auth
    headers = INTERNAL_AUTH_HEADER # Use internal auth header
    print(f"Fetching user email for {user_id} from: {user_service_url}")

    try:
        response = requests.get(user_service_url, headers=headers, timeout=5)
        print(f"User service response status for email fetch: {response.status_code}")

        if response.status_code == 404:
            print(f"User not found in user-service for ID: {user_id}")
            return None
        if response.status_code == 401 or response.status_code == 403:
             print(f"Authorization error fetching user email for ID: {user_id}. Check INTERNAL_API_KEY match.")
             # This indicates an internal auth issue
             return None # Or raise an internal error depending on desired strictness

        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        user_data = response.json()

        if not user_data or "email" not in user_data:
            print(f"Email not found in user-service response for ID: {user_id}")
            return None

        return user_data["email"]
    except requests.exceptions.Timeout:
        print(f"Timeout fetching user email from {user_service_url}")
        return None # Treat timeout as email not found for now
    except requests.exceptions.RequestException as e:
        print(f"User service request failed for email fetch: {e}")
        # Log the error but don't necessarily fail the payment process
        return None
    except Exception as e:
        print(f"Unexpected error fetching user email: {e}")
        print(traceback.format_exc())
        return None


def trigger_send_email(recipient_email: str, subject: str, html_body: str):
    """Makes an internal API call to the User Service to send an email."""
    send_email_url = f"{USER_SERVICE_URL}/internal/send-email"
    # Combine Content-Type with the defined auth header
    headers = {"Content-Type": "application/json", **INTERNAL_AUTH_HEADER}
    payload = {
        "recipient_email": recipient_email,
        "subject": subject,
        "html_body": html_body
    }
    print(f"Triggering email send via user-service to: {recipient_email} with headers: {list(headers.keys())}") # Don't log the key value

    try:
        response = requests.post(send_email_url, headers=headers, json=payload, timeout=10)
        print(f"User service email send response status: {response.status_code}")

        # Check specifically for 401/403
        if response.status_code == 401 or response.status_code == 403:
            print(f"Authorization error sending email request to {send_email_url}. Check INTERNAL_API_KEY match.")
            return False

        response.raise_for_status()
        print(f"Email request successfully sent to user-service for {recipient_email}")
        return True
    except requests.exceptions.Timeout:
         print(f"Timeout sending email request to {send_email_url}")
         return False # Email sending failed
    except requests.exceptions.RequestException as e:
        print(f"Failed to trigger email send via user-service: {e}")
        if e.response is not None:
             print(f"User-service Response: {e.response.text}")
        return False # Email sending failed
    except Exception as e:
        print(f"Unexpected error triggering email send: {e}")
        print(traceback.format_exc())
        return False # Email sending failed 