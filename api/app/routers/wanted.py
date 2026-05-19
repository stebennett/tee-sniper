"""CRUD endpoints for wanted tee-time requests."""

import datetime
import logging
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError

from app.dependencies import get_current_session, get_wanted_store
from app.models.responses import ErrorResponse
from app.models.wanted import (
    CreateOneShotRequest,
    CreateRecurringRequest,
    PatchWantedRequest,
    WantedKind,
    WantedResponse,
    WantedSlot,
    WantedStatus,
)
from app.services.wanted_store import WantedStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wanted", tags=["Wanted"])


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


@router.post(
    "",
    response_model=WantedResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired session"},
        422: {"model": ErrorResponse, "description": "Invalid request body"},
    },
)
async def create_wanted(
    kind: WantedKind = Query(...),
    body: dict = Body(default=None),
    _session: dict = Depends(get_current_session),
    store: WantedStore = Depends(get_wanted_store),
) -> WantedResponse:
    try:
        if kind is WantedKind.ONE_SHOT:
            req = CreateOneShotRequest.model_validate(body or {})
            extra = dict(kind=kind, target_date=req.target_date)
        else:
            req = CreateRecurringRequest.model_validate(body or {})
            extra = dict(kind=kind, day_of_week=req.day_of_week,
                         end_date=req.end_date)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    now = _now()
    slot = WantedSlot(
        id=str(uuid.uuid4()),
        start_time=req.start_time,
        end_time=req.end_time,
        num_slots=req.num_slots,
        partners=req.partners,
        credentials=req.credentials,
        notify=req.notify,
        status=WantedStatus.PENDING,
        attempts=[],
        created_at=now,
        updated_at=now,
        **extra,
    )
    await store.create(slot)
    return WantedResponse.from_slot(slot)


@router.get(
    "",
    response_model=list[WantedResponse],
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired session"},
    },
)
async def list_wanted(
    status_filter: WantedStatus | None = Query(default=None, alias="status"),
    _session: dict = Depends(get_current_session),
    store: WantedStore = Depends(get_wanted_store),
) -> list[WantedResponse]:
    slots = await store.list_all()
    if status_filter is not None:
        slots = [s for s in slots if s.status is status_filter]
    return [WantedResponse.from_slot(s) for s in slots]


async def _require(store: WantedStore, slot_id: str) -> WantedSlot:
    slot = await store.get(slot_id)
    if slot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Wanted slot not found")
    return slot


@router.get(
    "/{slot_id}",
    response_model=WantedResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired session"},
        404: {"model": ErrorResponse, "description": "Wanted slot not found"},
    },
)
async def get_wanted(
    slot_id: str,
    _session: dict = Depends(get_current_session),
    store: WantedStore = Depends(get_wanted_store),
) -> WantedResponse:
    return WantedResponse.from_slot(await _require(store, slot_id))


@router.patch(
    "/{slot_id}",
    response_model=WantedResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired session"},
        404: {"model": ErrorResponse, "description": "Wanted slot not found"},
        422: {"model": ErrorResponse, "description": "Invalid patch"},
    },
)
async def patch_wanted(
    slot_id: str,
    patch: PatchWantedRequest,
    _session: dict = Depends(get_current_session),
    store: WantedStore = Depends(get_wanted_store),
) -> WantedResponse:
    slot = await _require(store, slot_id)
    fields = patch.model_dump(exclude_unset=True)

    disabled = fields.pop("disabled", None)
    for key, value in fields.items():
        setattr(slot, key, value)

    if disabled is True:
        slot.status = WantedStatus.DISABLED
    elif disabled is False and slot.status is WantedStatus.DISABLED:
        slot.status = WantedStatus.PENDING

    slot.updated_at = _now()
    # Re-validate window/kind invariants by reconstructing.
    try:
        slot = WantedSlot.model_validate(slot.model_dump())
    except ValidationError as exc:
        # Use str(exc) — exc.errors() may contain non-serializable objects
        # (e.g. ValueError in ctx) when pydantic value validators fire.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    await store.update(slot)
    return WantedResponse.from_slot(slot)


@router.delete(
    "/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired session"},
        404: {"model": ErrorResponse, "description": "Wanted slot not found"},
    },
)
async def delete_wanted(
    slot_id: str,
    _session: dict = Depends(get_current_session),
    store: WantedStore = Depends(get_wanted_store),
) -> Response:
    deleted = await store.delete(slot_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Wanted slot not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
