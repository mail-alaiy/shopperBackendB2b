from fastapi import FastAPI
from app.routers import orders
from app.routers import health_check
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from mangum import Mangum
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
app.include_router(health_check.router)

@app.on_event("startup")
def startup_event():
    init_db()
 
handler = Mangum(app)