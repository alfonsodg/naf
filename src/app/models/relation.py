"""Relations between entries that cover the same event."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, UniqueConstraint

from app.db.base import Base


class EntryRelation(Base):
    """Two entries a stored report grouped together; neither entry is removed."""

    __tablename__ = "entry_relations"
    __table_args__ = (
        UniqueConstraint("entry_id", "related_entry_id", "report_id", name="uq_entry_relations_pair_report"),
    )

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(Integer, index=True, nullable=False)
    related_entry_id = Column(Integer, index=True, nullable=False)
    kind = Column(String(20), default="related", nullable=False)
    report_id = Column(Integer, nullable=True)
    score = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)
