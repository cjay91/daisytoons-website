from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from app import payhere
from app.api.deps import DB, Mailer
from app.config import get_settings
from app.errors import NotFound
from app.services import payments

router = APIRouter(prefix="/payments", tags=["payments"])


async def _form(request: Request) -> dict[str, str]:
    form = await request.form()
    return {key: str(value) for key, value in form.items()}


@router.post("/payhere/notify", response_class=PlainTextResponse)
async def payhere_notify(request: Request, db: DB, mailer: Mailer) -> str:
    """PayHere calls this server to server with each payment result."""
    fields = await _form(request)
    await run_in_threadpool(payments.handle_notification, db, mailer, "payhere", fields)
    # Always 200: the outcome is logged in payment_events, and the caller learns nothing.
    return "OK"


def _require_fake_gateway() -> None:
    settings = get_settings()
    if settings.payment_provider != "fake" or settings.environment == "production":
        raise NotFound("Not found.")


@router.post("/fake/checkout", response_class=HTMLResponse)
async def fake_checkout(request: Request) -> str:
    """A stand-in for PayHere's payment page, for local development."""
    _require_fake_gateway()
    fields = await _form(request)
    keep = ["order_id", "amount", "currency", "return_url", "cancel_url"]
    hidden = "".join(
        f'<input type="hidden" name="{name}" value="{escape(fields.get(name, ""))}">'
        for name in keep
    )

    def button(status_code: str, label: str) -> str:
        return f'<button name="status_code" value="{status_code}">{label}</button>'

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Fake payment</title></head>
<body style="font-family: sans-serif; max-width: 30rem; margin: 3rem auto">
<h1>Fake payment gateway</h1>
<p>Local development only. No money moves.</p>
<p>Order {escape(fields.get("order_id", ""))}:
{escape(fields.get("currency", ""))} {escape(fields.get("amount", ""))}</p>
<form method="post" action="complete">{hidden}
{button(payhere.SUCCESS, "Pay")} {button(payhere.CANCELLED, "Cancel")}
{button(payhere.FAILED, "Fail")}
</form></body></html>"""


@router.post("/fake/complete")
async def fake_complete(request: Request, db: DB, mailer: Mailer) -> RedirectResponse:
    _require_fake_gateway()
    form = await _form(request)
    status_code = form.get("status_code", payhere.FAILED)
    fields = payments.fake_notification(
        form.get("order_id", ""), form.get("amount", ""), form.get("currency", ""), status_code
    )
    await run_in_threadpool(payments.handle_notification, db, mailer, "fake", fields)
    target = form.get("return_url") if status_code == payhere.SUCCESS else form.get("cancel_url")
    settings = get_settings()
    # Only send the browser back to our own storefront.
    if not target or not target.startswith(settings.storefront_url.rstrip("/") + "/"):
        target = settings.storefront_url
    return RedirectResponse(target, status_code=303)
