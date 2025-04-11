import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# PhonePe API Credentials and Endpoints

# Merchant ID 
merchant_id = os.getenv("PHONEPE_MERCHANT_ID", "PGTESTPAYUAT86")

# Salt Key
salt_key = os.getenv("PHONEPE_SALT_KEY", "96434309-7796-489d-8924-ab56988a6076")

# Salt Index
salt_index = os.getenv("PHONEPE_SALT_INDEX", "1")

# PhonePe API Base URL
base_url = os.getenv("PHONEPE_BASE_URL", "https://api-preprod.phonepe.com/apis/pg-sandbox")

# Payment Endpoint (Derived from base_url)
payment_url = f"{base_url}/pg/v1/pay"

# Status Check Endpoint Prefix
status_endpoint = "/pg/v1/status"

# Webhook URL 
webhook_url = os.getenv("PHONEPE_WEBHOOK_URL", "https://webhook.site/cd8af36c-a40e-467c-a592-4a7cf10ab4c6")

# Redirect URL
redirect_url = os.getenv("PHONEPE_REDIRECT_URL", "http://localhost:5173/order-success")