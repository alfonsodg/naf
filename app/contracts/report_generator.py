from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class Citation(BaseModel):
    entry_id: str
    entry_url: str
    title: str
    author: Optional[str] = None
    quote: Optional[str] = None
    relevance: float = 1.0


class DigestStory(BaseModel):
    title: str
    summary: str
    claims: List[str]
    citations: List[Citation]
    pub_type: Optional[str] = None
    entities: List[Dict[str, Any]] = []


class Digest(BaseModel):
    title: str
    summary: str
    period_start: str
    period_end: str
    filters: Dict[str, Any] = {}
    cursor: Optional[str] = None
    stories: List[DigestStory]
    version: str = "1.0"


class ReportGenerator(ABC):
    @abstractmethod
    async def generate(
        self,
        entries: List[Dict[str, Any]],
        filters: Dict[str, Any],
        since_last: Optional[str] = None,
    ) -> Digest:
        pass

    @abstractmethod
    def validate_citations(self, digest: Digest, entries: List[Dict[str, Any]]) -> bool:
        pass
