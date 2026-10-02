"""FastAPI application - routes, templates, background jobs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import database as db
from . import marketing, payments
from .config import PLANS, STATIC_DIR, TEMPLATES_DIR, settings
from .localization import (DEFAULT_LANGUAGE, DEFAULT_TONE, LANGUAGES, TONES,
                           is_rtl, language_name, tone_label, valid_language,
                           valid_tone)
from .shredder import shred

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger("viral_shredder")

# Shared bearer token a real gateway would sign webhooks with. Empty = no check
# (local demo only - set WEBHOOK_TOKEN before exposing the port publicly).
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(payments.settlement_loop())
    log.info("database ready; payment settlement loop started (demo=%s)",
             settings.payment_demo_mode)
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(
    title="Viral Shredder - AI Content Shredder",
    version="1.0.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.filters["from_json"] = json.loads
templates.env.filters["number_format"] = lambda value, ndigits=0, sep=",": (
    f"{float(value):,.{int(ndigits)}f}".replace(",", sep)
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --------------------------------------------------------------- helpers
def _ctx(request: Request, **extra) -> dict:
    base = {
        "request": request,
        "settings": settings,
        "plans": PLANS,
        "whatsapp_link": f"https://wa.me/{settings.whatsapp_number}",
        "telegram_link": f"https://t.me/{settings.telegram_username}",
        "tones": TONES,
        "languages": LANGUAGES,
        "default_tone": DEFAULT_TONE,
        "default_language": DEFAULT_LANGUAGE,
    }
    base.update(extra)
    return base


def _user_from(request: Request) -> int:
    """Demo session: the user id is held in an httpOnly cookie."""
    raw = request.cookies.get("vs_user")
    if not raw or not raw.isdigit():
        raise HTTPException(status_code=401, detail="No active session - please sign in.")
    return int(raw)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", _ctx(request))


@app.get("/signup", response_class=HTMLResponse)
async def signup_form(request: Request):
    return templates.TemplateResponse(request, "signup.html", _ctx(request))


@app.post("/signup")
async def signup(request: Request, email: str = Form(...),
                 tone: str = Form(""), language: str = Form("")):
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    user_id = db.get_or_create_user(email)
    user = db.get_user(user_id)
    # Carry the tone/language picked on the landing page through to the dashboard.
    params = []
    if tone:
        params.append(f"tone={valid_tone(tone)}")
    if language:
        params.append(f"lang={valid_language(language)}")
    target = "/dashboard" + ("?" + "&".join(params) if params else "")
    response = RedirectResponse(url=target, status_code=303)
    response.set_cookie("vs_user", str(user_id), httponly=True, max_age=60 * 60 * 24 * 30)
    response.set_cookie("vs_email", user["email"], max_age=60 * 60 * 24 * 30)
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_id = _user_from(request)
    user = db.get_user(user_id)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _ctx(request, user=user, jobs=db.recent_jobs(user_id), plan=PLANS[user["plan"]]),
    )


# ----------------------------------------------------------------- shredder
@app.post("/shred")
async def shred_endpoint(
    request: Request,
    url: str = Form(...),
    outputs: str = Form("seo_article,x_thread,linkedin_post"),
    tone: str = Form(DEFAULT_TONE),
    language: str = Form(DEFAULT_LANGUAGE),
):
    user_id = _user_from(request)
    user = db.get_user(user_id)
    plan = PLANS[user["plan"]]

    if tone not in TONES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tone. Choose one of: {', '.join(TONES)}.",
        )
    if language not in LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown language. Choose one of: {', '.join(LANGUAGES)}.",
        )

    wanted = [o.strip() for o in outputs.split(",") if o.strip()]
    blocked = [o for o in wanted if o not in plan["outputs"]]
    if blocked:
        raise HTTPException(
            status_code=403,
            detail=f"Your {plan['name']} plan does not include: {', '.join(blocked)}. Upgrade to Pro.",
        )

    if user["credits_used"] >= plan["credits_per_month"]:
        raise HTTPException(
            status_code=402,
            detail=(f"Monthly credit limit reached ({plan['credits_per_month']} on "
                    f"{plan['name']}). Upgrade to Pro for 150 credits."),
        )

    try:
        result = await asyncio.to_thread(shred, url.strip(), 0, tone, language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("shred failed")
        raise HTTPException(status_code=502, detail=f"Could not read that video: {exc}") from exc

    job_id = db.create_job(user_id, result.source_url, result.platform, result.title)
    payload = {
        "seo_article": result.seo_article if "seo_article" in wanted else {},
        "x_thread": result.x_thread if "x_thread" in wanted else [],
        "linkedin_post": result.linkedin_post if "linkedin_post" in wanted else "",
        "keywords": result.keywords,
        "meta": result.meta,
    }
    db.complete_job(job_id, payload)
    db.record_credit_use(user_id)

    log.info("shred ok job=%s platform=%s words=%s", job_id, result.platform,
             result.seo_article["word_count"])
    return {"job_id": job_id, "title": result.title, **payload}


@app.get("/job/{job_id}", response_class=HTMLResponse)
async def job_view(request: Request, job_id: int):
    user_id = _user_from(request)
    job = db.get_job(job_id)
    if not job or job["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Job not found.")
    return templates.TemplateResponse(request, "result.html", _ctx(request, job=job))


# ----------------------------------------------------------------- pricing
@app.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return templates.TemplateResponse(request, "pricing.html", _ctx(request))


@app.get("/upgrade", response_class=HTMLResponse)
async def upgrade_form(request: Request, network: str = Query("trc20")):
    user_id = _user_from(request)
    order = payments.create_order(user_id, plan_id="pro", network_id=network)
    return templates.TemplateResponse(request, "checkout.html", _ctx(request, order=order))


@app.get("/checkout/{payment_id}", response_class=HTMLResponse)
async def checkout_status(request: Request, payment_id: int):
    user_id = _user_from(request)
    row = db.get_payment(payment_id)
    if not row or row["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Order not found.")
    return templates.TemplateResponse(request, "checkout.html",
                                       _ctx(request, order=row,
                                            networks=payments.networks()))


@app.get("/api/payment/{payment_id}/status")
async def payment_status(payment_id: int):
    row = db.get_payment(payment_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found.")
    return {"payment_id": payment_id, "status": row["status"],
            "demo": settings.payment_demo_mode}


@app.post("/api/payment/{payment_id}/confirm")
async def confirm_payment(payment_id: int):
    """Manual settlement (used when PAYMENT_DEMO_MODE=0, or by support staff)."""
    if not payments.admin_confirm(payment_id):
        raise HTTPException(
            status_code=409,
            detail="Order could not be confirmed (already settled or missing).",
        )
    return {"status": "paid", "plan": "pro"}


@app.post("/webhook/payment")
async def payment_webhook(request: Request):
    """Webhook shape for a real gateway.

    Expected JSON: {"order_ref": "...", "tx_hash": "...", "amount": 9.0, "currency": "USDT"}
    """
    if WEBHOOK_TOKEN and request.headers.get("authorization", "") != f"Bearer {WEBHOOK_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")
    body = await request.json()
    order_ref = body.get("order_ref")
    row = db.get_payment_by_ref(order_ref) if order_ref else None
    if not row:
        raise HTTPException(status_code=404, detail="Unknown order.")
    if row["status"] == "pending":
        db.confirm_payment(row["id"], tx_hash=body.get("tx_hash", "webhook"))
        db.set_user_plan(row["user_id"], "pro")
        log.info("webhook settled order %s", order_ref)
    return {"status": "paid"}


# ---------------------------------------------------------------- marketing
@app.get("/marketing", response_class=HTMLResponse)
async def marketing_page(request: Request):
    return templates.TemplateResponse(
        request,
        "marketing.html",
        _ctx(request, directories=marketing.load_directories(),
             submissions=db.recent_submissions()),
    )


@app.post("/api/marketing/run")
async def marketing_run(request: Request, dry_run: bool = Form(False)):
    _user_from(request)  # require a session
    results = await asyncio.to_thread(marketing.run_submission, dry_run)
    return marketing.summary(results)


# ----------------------------------------------------------------- support
@app.get("/support", response_class=HTMLResponse)
async def support_page(request: Request):
    return templates.TemplateResponse(request, "support.html", _ctx(request))


@app.get("/health")
async def health():
    return {"status": "ok", "demo_payments": settings.payment_demo_mode}
