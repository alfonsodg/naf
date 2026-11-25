"""Related coverage stored by a report."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.services.relations import related_entries

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/entries/{entry_id}/related")
async def related(entry_id: int, session: SessionDep) -> dict[str, Any]:
    """Return the entries a stored report grouped with this one."""
    return {"data": related_entries(session, entry_id)}
