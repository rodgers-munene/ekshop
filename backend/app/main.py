import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.limiter import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
from app.routers import auth, users, shop, payments, admin, messaging, investor
from app.routers.catalog import categories_router, products_router
from app.routers.commerce import cart_router, checkout_router, orders_router
from app.routers.delivery import router as delivery_router
from app.routers.recommendations import router as recommendations_router
from app.routers.hero import router as hero_router
from app.routers.deals import router as deals_router
from app.routers.notifications import router as notifications_router

app = FastAPI(title="Ekshop API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
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
app.include_router(admin.router)
app.include_router(investor.router)
app.include_router(messaging.router)
app.include_router(hero_router)
app.include_router(deals_router)
app.include_router(notifications_router)


@app.get("/")
def health():
    return {"status": "ok", "message": "Ekshop API is running"}
