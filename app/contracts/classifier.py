from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class Classification(BaseModel):
    category: Optional[str] = None
    categories: List[str] = []
    tags: List[str] = []
    pub_type: Optional[str] = None
    is_official: Optional[bool] = None
    confidence: float = 0.0
    uncertainty: bool = False
    review_needed: bool = False
    ai_enrichment: Optional[Dict[str, Any]] = None
    rationale: str = ""


class Classifier(ABC):
    @abstractmethod
    async def classify(self, item: Dict[str, Any]) -> Classification:
        pass

    @abstractmethod
    async def classify_batch(self, items: List[Dict[str, Any]]) -> List[Classification]:
        pass
