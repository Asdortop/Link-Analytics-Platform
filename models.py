from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from datetime import datetime
class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(String, nullable=False)
    short_code = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    clicks = Column(Integer, default=0)