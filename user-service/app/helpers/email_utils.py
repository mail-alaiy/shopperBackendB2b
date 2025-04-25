import resend
import os
from dotenv import load_dotenv
import datetime

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
if not RESEND_API_KEY:
    raise ValueError("RESEND_API_KEY not found in environment variables")

resend.api_key = RESEND_API_KEY

# Configure your sender email address
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "onboarding@resend.dev") # Replace with your verified domain sender if needed

def send_verification_email(recipient_email: str, verification_link: str, logoUrl: str = "https://b2b.shopperr.in/Shopperr%20white%20logo.png"):
    """Sends a verification email to the user."""
    try:
        current_year = datetime.datetime.now().year
        params = {
            "from": SENDER_EMAIL,
            "to": [recipient_email],
            "subject": "Verify Your Email Address",
            "html": f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Verify Your Email Address</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #ffffff; }} /* White background */
            .container {{ max-width: 600px; margin: 20px auto; background-color: #ffffff; border: 1px solid #cccccc; border-radius: 8px; overflow: hidden; }} /* White container, light gray border */
            .header {{ background-color: #06184b; padding: 20px; text-align: center; }} /* Blue header */
            .header img {{ max-width: 150px; }}
            .content {{ padding: 30px; color: #06184b; line-height: 1.6; }} /* Blue text */
            .content h1 {{ color: #06184b; font-size: 24px; margin-bottom: 20px; }} /* Blue heading */
            .content p {{ margin-bottom: 15px; }}
            .button {{ display: inline-block; background-color: #ffd701; color: #06184b; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; text-align: center; }} /* Yellow button, Blue text */
            .button:hover {{ background-color: #e6c300; }} /* Darker yellow hover */
            .footer {{ background-color: #e0f7ff; padding: 20px; text-align: center; font-size: 12px; color: #06184b; }} /* Very light blue footer, Blue text */
            .footer p {{ margin: 5px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="{logoUrl}" alt="Shopperr Logo">
            </div>
            <div class="content">
                <h1>Verify Your Email Address</h1>
                <p>Thank you for registering with Shopperr!</p>
                <p>Please click the button below to verify your email address and complete your registration:</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{verification_link}" class="button" style="color: #06184b;">Verify Email</a>
                </p>
                <p>If you did not request this registration, please ignore this email. Your account will not be activated.</p>
                <p>This link will expire in 24 hours.</p>
            </div>
            <div class="footer">
                <p>&copy; {current_year} - Mar 2030 One Stop Fashions Pvt Ltd. All rights reserved</p>
                <p>Shopperr Inc.- Building No. 225, Phase IV, Udyog Vihar, Gurugram. Haryana, India. 122001</p>
            </div>
        </div>
    </body>
    </html>
            """,
        }
        email = resend.Emails.send(params)
        print(f"Verification email sent: {email}")
        return email
    except Exception as e:
        print(f"Error sending verification email: {e}")
        raise e

def send_confirmation_email(recipient_email: str, logoUrl: str = "https://b2b.shopperr.in/Shopperr%20white%20logo.png"):
    """Sends a confirmation email after successful verification."""
    try:
        current_year = datetime.datetime.now().year
        login_link = "https://b2b.shopperr.in/auth" # Define the login link URL
        params = {
            "from": SENDER_EMAIL,
            "to": [recipient_email],
            "subject": "Welcome! Your Email is Verified",
            "html": f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Email Verified - Welcome to Shopperr!</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #ffffff; }} /* White background */
            .container {{ max-width: 600px; margin: 20px auto; background-color: #ffffff; border: 1px solid #cccccc; border-radius: 8px; overflow: hidden; }} /* White container, light gray border */
            .header {{ background-color: #06184b; padding: 20px; text-align: center; }} /* Blue header */
            .header img {{ max-width: 150px; }}
            .content {{ padding: 30px; color: #06184b; line-height: 1.6; }} /* Blue text */
            .content h1 {{ color: #06184b; font-size: 24px; margin-bottom: 20px; }} /* Blue heading */
            .content p {{ margin-bottom: 15px; }}
            .button {{ display: inline-block; background-color: #ffd701; color: #06184b; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold; text-align: center; }} /* Yellow button, Blue text */
            .button:hover {{ background-color: #e6c300; }} /* Darker yellow hover */
            .footer {{ background-color: #e0f7ff; padding: 20px; text-align: center; font-size: 12px; color: #06184b; }} /* Very light blue footer, Blue text */
            .footer p {{ margin: 5px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="{logoUrl}" alt="Shopperr Logo">
            </div>
            <div class="content">
                <h1>Welcome to Shopperr!</h1>
                <p>Your email address has been successfully verified.</p>
                <p>You can now log in to your account and start exploring. Click the button below to go to the login page:</p>
                <p style="text-align: center; margin: 30px 0;">
                    <a href="{login_link}" class="button" style="color: #06184b;">Login to Shopperr</a>
                </p>
                <p>Thank you for joining us!</p>
                <p>If you have any questions, feel free to contact our support team.</p>
            </div>
            <div class="footer">
                 <p>&copy; {current_year} - Mar 2030 One Stop Fashions Pvt Ltd. All rights reserved</p>
                 <p>Shopperr Inc.- Building No. 225, Phase IV, Udyog Vihar, Gurugram. Haryana, India. 122001</p>
            </div>
        </div>
    </body>
    </html>
            """,
        }
        email = resend.Emails.send(params)
        print(f"Confirmation email sent: {email}")
        return email
    except Exception as e:
        print(f"Error sending confirmation email: {e}")