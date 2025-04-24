from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import user
from app.database import Base, engine
from app import models
from mangum import Mangum
Base.metadata.create_all(bind=engine)

app = FastAPI(title="User Service", root_path="/user")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)

@app.get("")
def read_root():
    return {"message": "User Service is running"}

handler = Mangum(app)