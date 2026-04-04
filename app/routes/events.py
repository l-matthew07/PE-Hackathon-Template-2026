import json
from datetime import datetime

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.lib.utils import format_datetime, parse_pagination
from app.models.event import Event

events_bp = Blueprint("events", __name__, url_prefix="/events")

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
    return jsonify([_serialize_event(event) for event in events]), 200


@events_bp.post("")
def create_event():
    payload = request.get_json(silent=True) or {}

    url_id = payload.get("url_id")
    user_id = payload.get("user_id")
    event_type = (payload.get("event_type") or "").strip()
    details = payload.get("details")
    timestamp = payload.get("timestamp")

    if not url_id or not user_id or not event_type:
        return jsonify(error="url_id, user_id, and event_type are required"), 400

    if timestamp:
        try:
            parsed_timestamp = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except ValueError:
            return jsonify(error="timestamp must be ISO-8601"), 400
    else:
        parsed_timestamp = datetime.utcnow()

    serialized_details = details
    if isinstance(details, (dict, list)):
        serialized_details = json.dumps(details)

    try:
        event = Event.create(
            url_id=url_id,
            user_id=user_id,
            event_type=event_type,
            timestamp=parsed_timestamp,
            details=serialized_details,
        )
    except IntegrityError as exc:
        return jsonify(error=str(exc)), 400

    return jsonify(_serialize_event(event)), 201