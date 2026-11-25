"""NAF-owned classification records and the model mentions they evidence.

The reader owns the entry; NAF owns the reading it makes of the entry. A row
marked ``source="user"`` belongs to the user and is never overwritten by a new
automatic pass.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text

from app.db.base import Base


class EntryClassification(Base):
    """One entry's suggested categories, type, confidence, and correction state.

    ``source`` distinguishes the automatic answer (``auto``) from the values the
    user saved (``user``). ``rationale`` keeps the model's explanation, and a
    user correction appends the automatic values it replaced, so the suggestion
    is never lost. ``model`` names the LLM that produced the automatic answer.
    """

    __tablename__ = "entry_classifications"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, unique=True, index=True, nullable=False)
    category = Column(String(100))
    categories = Column(JSON, default=list)
    tags = Column(JSON, default=list)
    pub_type = Column(String(100))
    is_official = Column(Boolean, nullable=True)
    confidence = Column(Float, default=0.0)
    uncertainty = Column(Boolean, default=False)
    review_needed = Column(Boolean, default=False)
    rationale = Column(Text)
    source = Column(String(20), default="auto", nullable=False)
    model = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EntryModelMention(Base):
    """One model an entry names, with the evidence the classifier found.

    ``change_type`` says whether the entry announces a new model
    (``new_model``), a revision of an existing one (``model_update``), or
    neither (``unknown``). ``official`` is null when the entry does not settle
    whether its own source is the creator's channel. ``evidence_quote`` is a
    literal fragment of the entry; an empty quote means the mention has no
    verbatim support and must be read as unverified.
    """

    __tablename__ = "entry_model_mentions"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    creator = Column(String(255))
    change_type = Column(String(50), default="unknown", nullable=False)
    official = Column(Boolean, nullable=True)
    evidence_quote = Column(Text)
    evidence_url = Column(String(500))
    confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
