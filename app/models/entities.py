from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean

from app.db.base import Base


class Creator(Base):
    __tablename__ = "creators"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(500))
    evidence_url = Column(String(500))
    verified = Column(Boolean, default=False)
    meta = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ModelEntity(Base):
    __tablename__ = "model_entities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    family = Column(String(255))
    modality = Column(String(100))  # text, vision, audio, video, multimodal
    weights_available = Column(Boolean, default=False)
    license = Column(String(100))
    languages = Column(JSON, default=[])
    parameters_billion = Column(Integer)
    evidence_url = Column(String(500))
    verified = Column(Boolean, default=False)
    creator_id = Column(Integer)
    meta = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
