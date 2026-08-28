from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from database import Base
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at    = Column(DateTime, default=utcnow)


class URL(Base):
    __tablename__ = "urls"

    id           = Column(Integer, primary_key=True, index=True)
    original_url = Column(String, nullable=False)
    short_code   = Column(String, unique=True, index=True, nullable=False)
    created_at   = Column(DateTime, default=utcnow)
    clicks       = Column(Integer, default=0)
    owner_id     = Column(Integer, ForeignKey("users.id"), nullable=True)


class Click(Base):
    __tablename__ = "clicks"

    id         = Column(Integer, primary_key=True, index=True)
    short_code = Column(String, index=True)
    clicked_at = Column(DateTime, default=utcnow)
    ip         = Column(String)           # ← bug fix: ip was collected but never stored
    country    = Column(String)
    device     = Column(String)
    browser    = Column(String)