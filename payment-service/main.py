
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.database import init_db
from dotenv import load_dotenv
import os
load_dotenv()
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

@app.on_event("startup")
def startup_event():
    init_db()
    
@app.get("/health-check")
async def root():
    return {"message": "Payment Service is running", "MONGO_URL": os.getenv("DB_HOST"), "MONGO_DB": os.getenv("DB_NAME")}
