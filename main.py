from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
import string
import random
from pydantic import BaseModel
import models
from database import engine, SessionLocal
from fastapi.responses import RedirectResponse
from datetime import datetime
models.Base.metadata.create_all(bind=engine)

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

@app.get("/ping")
def ping_test():
    return {"status": "ok"}

@app.get("/{code}")
def redirect_url(code: str, db: Session = Depends(get_db)):
    url_entry = db.query(models.URL).filter(models.URL.short_code == code).first()
    if not url_entry:
        raise HTTPException(status_code=404, detail="URL Not Found")
    url_entry.clicks += 1
    click = models.Click(
        short_code=code,
        clicked_at = datetime.now(),
        country="Unknown",
        device="Unknown",
        browser="Unknown"
    )
    db.add(click)
    db.commit()
    db.refresh(url_entry)
    return RedirectResponse(url=url_entry.original_url)
