from typing import List, Dict, Any, Optional
from app.contracts.report_generator import (
    ReportGenerator,
    Digest,
)


class DefaultReportGenerator(ReportGenerator):
    async def generate(
        self,
        entries: List[Dict[str, Any]],
        filters: Dict[str, Any],
        since_last: Optional[str] = None,
    ) -> Digest:
        return Digest(
            title="Informe",
            summary="Pendiente de implementación",
            period_start=filters.get("period_start", ""),
            period_end=filters.get("period_end", ""),
            filters=filters,
            stories=[],
        )

    def validate_citations(self, digest: Digest, entries: List[Dict[str, Any]]) -> bool:
        # Basic validation - no unreferenced claims
        return True
