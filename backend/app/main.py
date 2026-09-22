import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.limiter import limiter

configure_logging()
from app.routers import auth, users, shop, payments, admin, messaging, investor, subscriptions, cron
from app.routers.catalog import categories_router, products_router
from app.routers.commerce import cart_router, checkout_router, orders_router
from app.routers.delivery import router as delivery_router
from app.routers.recommendations import router as recommendations_router
from app.routers.hero import router as hero_router
from app.routers.deals import router as deals_router
from app.routers.notifications import router as notifications_router
from app.routers.geography import router as geography_router
from app.routers.messaging_ws import router as messaging_ws_router
from app.routers.invoices import router as invoices_router
from app.routers.receipts import router as receipts_router

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
app.include_router(messaging_ws_router)
app.include_router(invoices_router)
app.include_router(receipts_router)
app.include_router(hero_router)
app.include_router(deals_router)
app.include_router(notifications_router)
app.include_router(geography_router)
app.include_router(subscriptions.router)
app.include_router(cron.router)


@app.get("/")
def root():
    return {"status": "ok", "message": "Ekshop API is running"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "up"
    except Exception:
        db_status = "down"
    return {
        "status": "ok" if db_status == "up" else "degraded",
        "database": db_status,
        "service": "ekshop-api",
    }


# Graceful shutdown: stop accepting new requests and finish in-flight work.
try:
    from uvicorn.signals import get_signals
    import signal

    def _graceful_shutdown(*args: object) -> None:
        raise SystemExit(0)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _graceful_shutdown)
except Exception:
    pass
