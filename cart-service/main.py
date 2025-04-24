from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import cart
from app.routers import health_check
from mangum import Mangum
app = FastAPI(title="Cart Service")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cart.router)
app.include_router(health_check.router)


handler = Mangum(app)