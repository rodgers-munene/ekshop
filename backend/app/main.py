from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, users, shop, payments
from app.routers.catalog import categories_router, products_router
from app.routers.commerce import cart_router, checkout_router, orders_router
from app.routers.delivery import router as delivery_router
from app.routers.recommendations import router as recommendations_router

app = FastAPI(title="Ekshop API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(shop.router)
app.include_router(categories_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(checkout_router)
app.include_router(orders_router)
app.include_router(payments.router)
app.include_router(delivery_router)
app.include_router(recommendations_router)


@app.get("/")
def health():
    return {"status": "ok", "message": "Ekshop API is running"}
