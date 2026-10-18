from typing import List, Dict, Any
from app.contracts.classifier import Classifier, Classification


class DefaultClassifier(Classifier):
    async def classify(self, item: Dict[str, Any]) -> Classification:
        return Classification(
            category=None,
            uncertainty=True,
            review_needed=True,
            rationale="Default classifier - needs implementation",
        )

    async def classify_batch(self, items: List[Dict[str, Any]]) -> List[Classification]:
        return [await self.classify(item) for item in items]
