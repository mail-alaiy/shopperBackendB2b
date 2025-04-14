
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Import the router
from app.routers import payment

load_dotenv() # Load environment variables from .env file

app = FastAPI(title="Payment Service")

# Add CORS middleware if needed (adjust origins as necessary)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows all origins - adjust for production
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

# Include the payment router
app.include_router(payment.router, tags=["Payment"]) # Added and tag

@app.get("/health-check")
async def root():
    return {"message": "Payment Service is running"}
