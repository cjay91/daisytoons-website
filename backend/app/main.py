from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, cart, health, orders, payments, products, staff
from app.config import get_settings
from app.errors import register_error_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(products.router)
    app.include_router(staff.router)
    app.include_router(cart.router)
    app.include_router(orders.router)
    app.include_router(payments.router)
    return app


app = create_app()
