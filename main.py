from fastapi import FastAPI, Depends, HTTPException, Request
from requests import request
from sqlalchemy.orm import Session
import string
import random
from pydantic import BaseModel
import models
from database import engine, SessionLocal
from fastapi.responses import RedirectResponse
from datetime import datetime
models.Base.metadata.create_all(bind=engine)
from sqlalchemy import func
from user_agents import parse
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class URLCreate(BaseModel):
    original_url: str

def generate_short_url(length=6):
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))

@app.post("/shorten/")
def create_short_url(url_request: URLCreate, db: Session = Depends(get_db)):

    while True:  # ✅ better collision handling
        code = generate_short_url()
        existing_url = db.query(models.URL).filter(models.URL.short_code == code).first()
        if not existing_url:
            break

    new_url = models.URL(
        original_url=url_request.original_url,
        short_code=code
    )

    db.add(new_url)
    db.commit()
    db.refresh(new_url)

    return {
        "original_url": new_url.original_url,
        "short_url": f"http://127.0.0.1:8000/{new_url.short_code}"
    }

@app.get("/stats/{code}")
def get_stats(code:str, db: Session = Depends(get_db)):
    total_clicks = db.query(func.count(models.Click.id))\
        .filter(models.Click.short_code==code)\
        .scalar()
    
    clicks_per_day = db.query(
    func.date(models.Click.clicked_at),
    func.count(models.Click.id)
    ).filter(models.Click.short_code == code)\
    .group_by(func.date(models.Click.clicked_at))\
    .all()
    
    device_stats = db.query(
            models.Click.device,
            func.count(models.Click.id)
        ).filter(models.Click.short_code == code)\
        .group_by(models.Click.device)\
        .all()

    browser_stats = db.query(
        models.Click.browser,
        func.count(models.Click.id)
    ).filter(models.Click.short_code == code)\
    .group_by(models.Click.browser)\
    .all()

    country_stats = db.query(
        models.Click.country,
        func.count(models.Click.id)
    ).filter(models.Click.short_code==code)\
    .group_by(models.Click.country)\
    .all()

    return {
        "short_code": code,
        "total_clicks": total_clicks,
        "clicks_per_day": [
            {"date": str(d), "count": c}
            for d, c in clicks_per_day
        ],
        "device_stats": [
            {"device": d, "count": c}
            for d, c in device_stats
        ],
        "browser_stats": [
            {"browser": b, "count": c}
            for b,c in browser_stats
        ],
        "country_stats": [
            {"country": ctry, "count": c}
            for ctry,c in country_stats
        ]
    }

@app.get("/ping")
def ping_test():
    return {"status": "ok"}

@app.get("/{code}")
def redirect_url(code: str, request: Request, db: Session = Depends(get_db)):
    cached_url = r.get(code)
    if cached_url:
        og_url = cached_url
        url_entry = None
    else:
        url_entry = db.query(models.URL).filter(models.URL.short_code == code).first()
        if not url_entry:
            raise HTTPException(status_code=404, detail="URL Not Found")
        og_url = url_entry.original_url
        r.set(code,og_url,ex = 3600)
    user_agent_string = request.headers.get("user-agent", "")
    ua = parse(user_agent_string)
    device = "mobile" if ua.is_mobile else "desktop"
    browser = ua.browser.family
    country = "IN"
    click = models.Click(
        short_code=code,
        clicked_at = datetime.now(),
        country=country,
        device=device,
        browser=browser
    )
    db.add(click)
    if url_entry:
        url_entry.clicks += 1
    db.commit()
    if url_entry:
        db.refresh(url_entry)
    return RedirectResponse(url=og_url)
