from fastapi import FastAPI
from app.routers import products
from app.routers import categories

app = FastAPI()
app.include_router(products.router)
app.include_router(categories.router)
