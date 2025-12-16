import requests
import os
from fastapi import HTTPException, status
import traceback
import resend # Import resend

# Load User Service URL and Resend API Key
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "onboarding@resend.dev") # Default sender if not set

if not USER_SERVICE_URL:
    raise ValueError("USER_SERVICE_URL environment variable not set.")
if not RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY environment variable not set.")
if not SENDER_EMAIL:
     print("Warning: SENDER_EMAIL environment variable not set. Using default.")


# Initialize Resend Client
resend.api_key = RESEND_API_KEY

# Placeholder for internal authentication for User Service
USER_SERVICE_INTERNAL_KEY = os.getenv("USER_SERVICE_INTERNAL_KEY")
if not USER_SERVICE_INTERNAL_KEY:
    print("CRITICAL WARNING: USER_SERVICE_INTERNAL_KEY not set. Internal calls to User Service will likely fail.")
    # Set a default or handle appropriately if missing, depending on security requirements
    USER_SERVICE_INTERNAL_KEY = "default-insecure-key" # Example: Replace or remove in production

INTERNAL_AUTH_HEADER = {"X-Internal-API-Key": USER_SERVICE_INTERNAL_KEY}

# --- Helper Functions ---

def _fetch_user_data_from_service(user_id: str) -> dict | None:
    """Internal helper to fetch raw user data from the User Service."""
    user_service_url = f"{USER_SERVICE_URL}/internal/user/{user_id}"
    headers = INTERNAL_AUTH_HEADER
    print(f"Fetching user data for {user_id} from: {user_service_url}")

    try:
        response = requests.get(user_service_url, headers=headers, timeout=5)
        print(f"User service response status for user data fetch: {response.status_code}")

        if response.status_code == status.HTTP_404_NOT_FOUND:
            print(f"User not found in user-service for ID: {user_id}")
            return None
        if response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]:
             print(f"Authorization error fetching user data for ID: {user_id}. Check USER_SERVICE_INTERNAL_KEY.")
             # This indicates an internal auth issue, critical failure
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal service communication error (Auth)")

        response.raise_for_status() # Raise HTTPError for other bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.Timeout:
        print(f"Timeout fetching user data from {user_service_url}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="User service request timed out")
    except requests.exceptions.RequestException as e:
        print(f"User service request failed for user data fetch: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to connect to user service")
    except Exception as e:
        print(f"Unexpected error fetching user data: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error fetching user data")


def get_user_email(user_id: str) -> str | None:
    """Fetches user email from the User Service using user ID."""
    try:
        user_data = _fetch_user_data_from_service(user_id)
        if user_data and "email" in user_data:
            return user_data["email"]
        else:
            print(f"Email not found in user-service response for ID: {user_id}")
            return None
    except HTTPException as e:
        # Log the error originated from the fetch function but return None
        # as the primary goal here is just to get the email if possible.
        # The caller (e.g., webhook) might decide how critical this is.
        print(f"Could not retrieve user data due to HTTP error: {e.detail}")
        return None
    except Exception as e:
        # Catch any other unexpected errors during processing
        print(f"Unexpected error processing user data for email: {e}")
        print(traceback.format_exc())
        return None


def send_email_with_resend(recipient_email: str, subject: str, html_body: str) -> bool:
    """Sends an email using the Resend service."""
    if not recipient_email:
        print("Error: No recipient email provided for sending.")
        return False

    print(f"Attempting to send email via Resend to: {recipient_email} with subject: {subject}")
    params = {
        "from": SENDER_EMAIL,
        "to": [recipient_email],
        "subject": subject,
        "html": html_body,
    }
    try:
        email_response = resend.Emails.send(params)
        print(f"Resend email response status: {email_response.get('id')}") # Log Resend ID on success
        # Assuming success if no exception is raised and we get an ID back
        return bool(email_response.get('id'))
    except Exception as e:
        # Log the error from resend API
        print(f"Error sending email via Resend to {recipient_email}: {e}")
        print(traceback.format_exc())
        return False