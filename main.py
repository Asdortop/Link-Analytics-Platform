import logging
import os
import secrets
import string

# ── Logging — set up before anything else loads ───────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Show WARNING+ from our app, suppress noisy library logs
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("passlib").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from database import engine, SessionLocal
from auth import get_current_user, get_current_user_optional
from rate_limiter import rate_limit
from routers.auth_router import router as auth_router

# pyrefly: ignore [missing-import]
from user_agents import parse
from worker_config import q, r

# Create all tables (including new users table)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="LinkLens", description="URL shortener with async analytics")

# ── CORS — allow React dashboard on localhost:5173 ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)


# ── Global exception handler — print ALL 500s to terminal ────────────────────
from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: FastAPIRequest, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s\n%s",
        request.method, request.url.path,
        traceback.format_exc()
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {str(exc)}"}
    )


# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

# ── DB dependency ─────────────────────────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Schemas ───────────────────────────────────────────────────────────────────
class URLCreate(BaseModel):
    original_url: HttpUrl
    custom_code: str | None = None   # optional vanity URL (e.g. "launch2025")


# ── Reserved codes — these conflict with existing routes ─────────────────────
RESERVED_CODES = {
    "shorten", "stats", "ping", "docs", "redoc", "openapi.json",
    "auth", "register", "login", "refresh", "favicon.ico",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def generate_short_code(length: int = 6) -> str:
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))  # ← bug fix: secrets not random


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post(
    "/shorten/",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60))],
)
def create_short_url(
    url_request: URLCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Shorten a URL. Requires authentication. Optionally accepts a custom short code."""

    if url_request.custom_code:
        code = url_request.custom_code.strip()

        # Validate format: 3-30 chars, alphanumeric + hyphens only
        if not (3 <= len(code) <= 30):
            raise HTTPException(status_code=400, detail="Custom code must be between 3 and 30 characters.")
        if not all(c.isalnum() or c == "-" for c in code):
            raise HTTPException(status_code=400, detail="Custom code can only contain letters, numbers, and hyphens.")

        # Block reserved route names
        if code.lower() in RESERVED_CODES:
            raise HTTPException(status_code=400, detail=f"'{code}' is a reserved word and cannot be used as a short code.")

        # Check for collision
        if db.query(models.URL).filter(models.URL.short_code == code).first():
            raise HTTPException(status_code=409, detail=f"'{code}' is already taken. Please choose a different code.")
    else:
        # Auto-generate a unique code
        while True:
            code = generate_short_code()
            if not db.query(models.URL).filter(models.URL.short_code == code).first():
                break

    new_url = models.URL(
        original_url=str(url_request.original_url),
        short_code=code,
        owner_id=current_user.id,
    )
    db.add(new_url)
    db.commit()
    db.refresh(new_url)

    return {
        "original_url": new_url.original_url,
        "short_url": f"{BASE_URL}/{new_url.short_code}",
    }


@app.get("/stats/{code}")
def get_stats(
    code: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Analytics for a short link. Only accessible by the owner."""
    url_entry = db.query(models.URL).filter(models.URL.short_code == code).first()
    if not url_entry:
        raise HTTPException(status_code=404, detail="Short code not found")   # ← bug fix: 404 on unknown code

    if url_entry.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this link")

    total_clicks = (
        db.query(func.count(models.Click.id))
        .filter(models.Click.short_code == code)
        .scalar()
    )

    clicks_per_day = (
        db.query(func.date(models.Click.clicked_at), func.count(models.Click.id))
        .filter(models.Click.short_code == code)
        .group_by(func.date(models.Click.clicked_at))
        .all()
    )

    device_stats = (
        db.query(models.Click.device, func.count(models.Click.id))
        .filter(models.Click.short_code == code)
        .group_by(models.Click.device)
        .all()
    )

    browser_stats = (
        db.query(models.Click.browser, func.count(models.Click.id))
        .filter(models.Click.short_code == code)
        .group_by(models.Click.browser)
        .all()
    )

    country_stats = (
        db.query(models.Click.country, func.count(models.Click.id))
        .filter(models.Click.short_code == code)
        .group_by(models.Click.country)
        .all()
    )

    return {
        "short_code": code,
        "total_clicks": total_clicks,
        "clicks_per_day": [{"date": str(d), "count": c} for d, c in clicks_per_day],
        "device_stats": [{"device": d, "count": c} for d, c in device_stats],
        "browser_stats": [{"browser": b, "count": c} for b, c in browser_stats],
        "country_stats": [{"country": ctry, "count": c} for ctry, c in country_stats],
    }


@app.get("/ping")
def ping_test():
    return {"status": "ok"}


@app.get("/{code}")
def redirect_url(code: str, request: Request, db: Session = Depends(get_db)):
    """Public redirect — no auth required."""
    # Layer 1: Redis cache
    cached_url = r.get(code)
    if cached_url:
        og_url = cached_url
    else:
        # Layer 2: Postgres B-tree lookup
        url_entry = db.query(models.URL).filter(models.URL.short_code == code).first()
        if not url_entry:
            raise HTTPException(status_code=404, detail="URL Not Found")
        og_url = url_entry.original_url
        r.set(code, og_url, ex=3600)

    # Parse User-Agent
    ua = parse(request.headers.get("user-agent", ""))
    device = "mobile" if ua.is_mobile else "desktop"
    browser = ua.browser.family

    # Real IP (proxy-aware)
    forwarded_for = request.headers.get("X-Forwarded-For")
    ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host

    click_data = {
        "short_code": code,
        "ip": ip,
        "device": device,
        "browser": browser,
    }

    q.enqueue("tasks.save_click", click_data)

    return RedirectResponse(url=og_url)
