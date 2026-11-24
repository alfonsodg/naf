"""Classification API: suggest topics, evidence model mentions, and take corrections.

The reader keeps owning the entries; this surface reads one of them on demand
and stores what the classifier makes of it. A row marked ``source="user"`` is
returned untouched by a later automatic pass, and an unconfigured model is
refused before the reader is touched.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.adapters.llm.classifier import LLMClassifier
from app.adapters.miniflux.client import MinifluxClient
from app.core.config import settings as app_settings
from app.core.exceptions import MinifluxAPIError, NafError
from app.core.ports.classifier import Classifier
from app.core.ports.feed_reader import FeedReader
from app.db.session import get_session
from app.routers.feeds import LimitQuery, PageQuery
from app.schemas.classification import (
    ClassificationCorrection,
    ClassificationDetailResponse,
    ClassificationListResponse,
    ClassificationPagination,
    ClassificationResponse,
    ClassificationView,
    ModelMentionView,
)
from app.schemas.errors import error_body
from app.services.classification import PRESERVED_NOTICE, ClassificationOutcome, ClassificationService

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]
ReviewQuery = Annotated[bool | None, Query(description="Filter by the review flag; omit to list every row")]


def _reader() -> FeedReader:
    """Build the reader adapter for one request."""
    return MinifluxClient()


def _classifier() -> Classifier:
    """Build the classifier through the LLM adapter."""
    return LLMClassifier(app_settings)


def _service(session: Session) -> ClassificationService:
    """Build the classification service for one request."""
    return ClassificationService(session, _reader(), _classifier())


def _response(outcome: ClassificationOutcome) -> ClassificationResponse:
    """Project one stored outcome with its mentions and the preservation notice."""
    return ClassificationResponse(
        data=ClassificationView.model_validate(outcome.classification),
        models=[ModelMentionView.model_validate(row) for row in outcome.models],
        notice=PRESERVED_NOTICE if outcome.preserved else None,
    )


def _not_stored(entry_id: int) -> HTTPException:
    """Build the documented 404 for an entry that was never classified."""
    return HTTPException(
        status_code=404,
        detail=error_body("CLASSIFICATION_NOT_FOUND", f"entry {entry_id} has no stored classification"),
    )


@router.post("/entries/{entry_id}/classify", status_code=201)
async def classify_entry(entry_id: Annotated[int, Path(ge=1)], session: SessionDep) -> ClassificationResponse:
    """Classify one reader entry and store the suggestion with its mentions.

    An unconfigured model is refused before the reader is called. A reader that
    does not have the entry answers 404; any provider or validation failure
    answers 502 without exposing the provider's detail. When the stored row was
    corrected by the user, it is returned unchanged and the response says so.
    """
    if not app_settings.llm_model:
        raise HTTPException(
            status_code=503,
            detail=error_body("CLASSIFIER_NOT_CONFIGURED", "no LLM model is configured for classification"),
        )
    try:
        outcome = await _service(session).classify(entry_id)
    except MinifluxAPIError as exc:
        if exc.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=error_body("ENTRY_NOT_FOUND", f"the reader does not have entry {entry_id}"),
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=error_body("MINIFLUX_UNAVAILABLE", str(exc)),
        ) from exc
    except NafError as exc:
        # The provider failure and the invalid answer share one public outcome.
        raise HTTPException(
            status_code=502,
            detail=error_body("CLASSIFICATION_FAILED", "the entry could not be classified"),
        ) from exc
    return _response(outcome)


@router.get("/entries/{entry_id}/classification")
async def read_classification(
    entry_id: Annotated[int, Path(ge=1)], session: SessionDep
) -> ClassificationDetailResponse:
    """Return the stored classification with its mentions, or the documented 404."""
    outcome = _service(session).get(entry_id)
    if outcome is None:
        raise _not_stored(entry_id)
    return ClassificationDetailResponse(
        data=ClassificationView.model_validate(outcome.classification),
        models=[ModelMentionView.model_validate(row) for row in outcome.models],
    )


@router.patch("/entries/{entry_id}/classification")
async def correct_classification(
    entry_id: Annotated[int, Path(ge=1)],
    payload: ClassificationCorrection,
    session: SessionDep,
) -> ClassificationResponse:
    """Apply a user correction and keep the automatic answer in the rationale.

    The user owns category, categories, tags, and publication type; confidence,
    officialness, review flags, and model mentions stay as the classifier left
    them. A body naming none of the four fields is refused as 422.
    """
    outcome = _service(session).correct(entry_id, payload)
    if outcome is None:
        raise _not_stored(entry_id)
    return _response(outcome)


@router.get("/classifications")
async def list_classifications(
    session: SessionDep,
    review_needed: ReviewQuery = None,
    page: PageQuery = 1,
    per_page: LimitQuery = 50,
) -> ClassificationListResponse:
    """List stored classifications newest first, optionally filtered by review flag."""
    rows, total = _service(session).list_review(review_needed, page, per_page)
    return ClassificationListResponse(
        data=[ClassificationView.model_validate(row) for row in rows],
        pagination=ClassificationPagination(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page if total else 0,
        ),
    )
