from fastapi import FastAPI
from app.routers import orders

app = FastAPI()
app.include_router(orders.router)
