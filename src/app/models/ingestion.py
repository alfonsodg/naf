from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from app.db.base import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(Integer, primary_key=True, index=True)
    adapter_name = Column(String(100), default="miniflux")
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    status = Column(String(50), default="running")  # running, success, failed
    entries_count = Column(Integer, default=0)
    errors = Column(JSON, default=[])
    error_summary = Column(Text)
    meta = Column(JSON, default={})
