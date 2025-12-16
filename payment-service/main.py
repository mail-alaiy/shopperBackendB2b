
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.database import init_db
from dotenv import load_dotenv
import os
from mangum import Mangum
load_dotenv()
from app.routers import payment
from app.routers import health_check

load_dotenv()

app = FastAPI(title="Payment Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(payment.router, tags=["Payment"])
app.include_router(health_check.router)

@app.on_event("startup")
def startup_event():
    init_db()
    
handler = Mangum(app)