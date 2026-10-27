from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    cart,
    health,
    orders,
    payments,
    products,
    purchasing,
    staff,
    staff_orders,
)
from app.config import get_settings
from app.errors import register_error_handlers
from app.errors_tracking import init_error_tracking

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def create_app() -> FastAPI:
    settings = get_settings()
    init_error_tracking("api")
    production = settings.environment == "production"
    # No public API docs in production.
    app = FastAPI(
        title=settings.app_name,
        docs_url=None if production else "/docs",
        redoc_url=None,
        openapi_url=None if production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(products.router)
    app.include_router(staff.router)
    app.include_router(staff_orders.router)
    app.include_router(cart.router)
    app.include_router(orders.router)
    app.include_router(payments.router)
    app.include_router(purchasing.router)
    return app


app = create_app()
