import resend
import os
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
if not RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY not found in environment variables")

resend.api_key = RESEND_API_KEY

# Configure your sender email address
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "onboarding@resend.dev") # Replace with your verified domain sender if needed

def send_verification_email(recipient_email: str, verification_link: str):
    """Sends a verification email to the user."""
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [recipient_email],
            "subject": "Verify Your Email Address",
            "html": f"""
                <p>Thank you for registering!</p>
                <p>Please click the link below to verify your email address:</p>
                <p><a href="{verification_link}">Verify Email</a></p>
                <p>If you did not request this, please ignore this email.</p>
            """,
        }
        email = resend.Emails.send(params)
        print(f"Verification email sent: {email}")
        return email
    except Exception as e:
        print(f"Error sending verification email: {e}")
        raise e

def send_confirmation_email(recipient_email: str):
    """Sends a confirmation email after successful verification."""
    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [recipient_email],
            "subject": "Welcome! Your Email is Verified",
            "html": """
                <p>Welcome!</p>
                <p>Your email address has been successfully verified.</p>
                <p>You can now log in to your account.</p>
                <p>Thank you for joining us!</p>
            """,
        }
        email = resend.Emails.send(params)
        print(f"Confirmation email sent: {email}")
        return email
    except Exception as e:
        print(f"Error sending confirmation email: {e}")