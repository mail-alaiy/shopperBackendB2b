from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import cart

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

@app.get("/")
def read_root():
    return {"message": "Cart Service is running"} 