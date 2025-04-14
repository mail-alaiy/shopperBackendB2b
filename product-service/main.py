from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import products
from app.routers import categories

app = FastAPI(title="Product Service")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(categories.router)

@app.get("/health-check")
def read_root():
    return {"message": "Product Service is running"}
