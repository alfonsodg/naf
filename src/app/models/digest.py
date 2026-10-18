from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Digest(Base):
    __tablename__ = "digests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    filters = Column(JSON, default={})
    cursor = Column(String(255))
    version = Column(String(50), default="1.0")
    status = Column(String(50), default="draft")  # draft, ready, failed
    has_audio = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stories = relationship("DigestStory", back_populates="digest", cascade="all, delete-orphan")
    audio_assets = relationship("AudioAsset", back_populates="digest")


class DigestStory(Base):
    __tablename__ = "digest_stories"

    id = Column(Integer, primary_key=True, index=True)
    digest_id = Column(Integer, ForeignKey("digests.id"), nullable=False)
    title = Column(String(255), nullable=False)
    summary = Column(Text)
    claims = Column(JSON, default=[])
    citations = Column(JSON, default=[])
    pub_type = Column(String(100))
    entities = Column(JSON, default=[])
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    digest = relationship("Digest", back_populates="stories")
