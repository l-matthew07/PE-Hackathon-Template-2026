import json

from flask import request
from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from app.lib.api import error_response, list_response
from app.lib.utils import format_datetime, normalize_pagination
from app.models.event import Event
from app.services.errors import ServiceError
from app.services.schemas import (
    BulkLoadResponse,
    ErrorEnvelope,
    EventCreatePayload,
    EventListQuery,
    EventListResponse,
    EventResponse,
)
from app.services.events_service import EventsService

events_tag = Tag(name="events")
events_bp = APIBlueprint("events", __name__, url_prefix="/events", abp_tags=[events_tag])
events_service = EventsService()

def _serialize_details(value: object):
    if value is None or value == "":
        return None
    if not isinstance(value, (str, bytes, bytearray)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _serialize_event(event: Event) -> dict:
    user_id = getattr(event, "user_id", None)
    if user_id is None:
        user_value = getattr(event, "user", None)
        user_id = getattr(user_value, "id", None) if user_value is not None else None

    return {
        "id": event.id,
        "url_id": event.url_id,
        "user_id": user_id,
        "event_type": event.event_type,
        "timestamp": format_datetime(event.timestamp),
        "details": _serialize_details(event.details),
    }


@events_bp.get("", responses={200: EventListResponse})
def list_events(query: EventListQuery):
    page, per_page = normalize_pagination(query.page, query.per_page)
    offset = (page - 1) * per_page

    db_query = Event.select()

    if query.user_id is not None:
        db_query = db_query.where(Event.user == query.user_id)

    if query.url_id is not None:
        db_query = db_query.where(Event.url_id == query.url_id)

    if query.event_type:
        db_query = db_query.where(Event.event_type == query.event_type)

    events = db_query.order_by(Event.id).limit(per_page).offset(offset)
    return list_response([_serialize_event(event) for event in events], page, per_page)


@events_bp.post("", responses={201: EventResponse, 400: ErrorEnvelope, 409: ErrorEnvelope})
def create_event(body: EventCreatePayload):
    try:
        event = events_service.create_event(body.model_dump())
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return _serialize_event(event), 201


@events_bp.post("/bulk", responses={200: BulkLoadResponse, 400: ErrorEnvelope})
def bulk_load_events():
    payload = request.get_json(silent=True) or {}
    filename = str(payload.get("file") or "events.csv").strip() or "events.csv"
    requested_count = payload.get("row_count")
    try:
        loaded_count = events_service.bulk_load_events(filename)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)
    return {"file": filename, "row_count": requested_count, "loaded": loaded_count}, 200