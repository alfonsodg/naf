from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class AudioAsset(Base):
    __tablename__ = "audio_assets"

    id = Column(Integer, primary_key=True, index=True)
    digest_id = Column(Integer, ForeignKey("digests.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_path = Column(Text, nullable=False)
    format = Column(String(10), default="mp3")
    duration_seconds = Column(Float)
    size_bytes = Column(Integer)
    checksum = Column(String(64))
    provider = Column(String(100))
    voice = Column(String(100))
    version = Column(String(50), default="1.0")
    is_immutable = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    digest = relationship("Digest", back_populates="audio_assets")
