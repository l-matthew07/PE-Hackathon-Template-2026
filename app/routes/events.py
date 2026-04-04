import json

from flask import Blueprint, jsonify, request

from app.lib.api import error_response, list_response
from app.lib.utils import format_datetime, parse_pagination
from app.models.event import Event
from app.services.errors import ServiceError
from app.services.events_service import EventsService

events_bp = Blueprint("events", __name__, url_prefix="/events")
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
    return {
        "id": event.id,
        "url_id": event.url.id if event.url is not None else None,
        "user_id": event.user.id if event.user is not None else None,
        "event_type": event.event_type,
        "timestamp": format_datetime(event.timestamp),
        "details": _serialize_details(event.details),
    }


@events_bp.get("")
def list_events():
    page, per_page = parse_pagination()
    offset = (page - 1) * per_page

    query = Event.select()

    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        query = query.where(Event.user == user_id)

    url_id = request.args.get("url_id", type=int)
    if url_id is not None:
        query = query.where(Event.url == url_id)

    event_type = request.args.get("event_type")
    if event_type:
        query = query.where(Event.event_type == event_type)

    events = query.order_by(Event.id).limit(per_page).offset(offset)
    return list_response([_serialize_event(event) for event in events], page, per_page)


@events_bp.post("")
def create_event():
    payload = request.get_json(silent=True) or {}

    try:
        event = events_service.create_event(payload)
    except ServiceError as exc:
        return error_response(exc.message, exc.code, exc.status, details=exc.details)

    return jsonify(_serialize_event(event)), 201