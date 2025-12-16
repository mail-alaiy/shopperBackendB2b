from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import products
from routers import categories
from routers import health_check
from mangum import Mangum
app = FastAPI(title="Product Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(categories.router)
app.include_router(health_check.router)

handler = Mangum(app)