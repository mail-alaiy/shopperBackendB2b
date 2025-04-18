from fastapi import FastAPI
from app.routers import orders
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(orders.router)


@app.on_event("startup")
def startup_event():
    init_db()
    
@app.get("/health-check")
def read_root():
    return {"message": "Cart Service is running"} 