from datetime import datetime

from flask_openapi3.blueprint import APIBlueprint
from flask_openapi3.models.tag import Tag

from app.lib.api import error_response
from app.lib.utils import format_datetime
from app.models.alert import Alert
from app.services.schemas import (
    AlertCreatePayload,
    AlertIdPath,
    AlertListQuery,
    AlertListResponse,
    AlertResponse,
    AlertUpdatePayload,
    ErrorEnvelope,
)

alerts_tag = Tag(name="alerts")
alerts_bp = APIBlueprint("alerts", __name__, url_prefix="/alerts", abp_tags=[alerts_tag])

_VALID_STATUSES = {"firing", "acknowledged", "resolved"}


def _serialize_alert(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "alert_name": alert.alert_name,
        "severity": alert.severity,
        "status": alert.status,
        "summary": alert.summary or None,
        "source": alert.source or None,
        "notes": alert.notes or None,
        "fired_at": format_datetime(alert.fired_at),
        "acknowledged_at": format_datetime(alert.acknowledged_at),
        "resolved_at": format_datetime(alert.resolved_at),
        "acknowledged_by": alert.acknowledged_by,
    }


@alerts_bp.get("", responses={200: AlertListResponse})
def list_alerts(query: AlertListQuery):
    q = Alert.select().order_by(Alert.id.desc())
    if query.status:
        q = q.where(Alert.status == query.status)
    if query.severity:
        q = q.where(Alert.severity == query.severity)
    return {"data": [_serialize_alert(a) for a in q]}, 200


@alerts_bp.post("", responses={201: AlertResponse, 400: ErrorEnvelope})
def create_alert(body: AlertCreatePayload):
    if not body.alert_name or not body.alert_name.strip():
        return error_response("alert_name is required", "VALIDATION_ERROR", 400)

    alert = Alert.create(
        alert_name=body.alert_name.strip(),
        severity=body.severity or "warning",
        status="firing",
        summary=body.summary or "",
        source=body.source or "",
        notes=body.notes or "",
        fired_at=datetime.utcnow(),
    )
    return _serialize_alert(alert), 201


@alerts_bp.get("/<int:alert_id>", responses={200: AlertResponse, 404: ErrorEnvelope})
def get_alert(path: AlertIdPath):
    alert = Alert.get_or_none(Alert.id == path.alert_id)
    if alert is None:
        return error_response("Alert not found", "NOT_FOUND", 404)
    return _serialize_alert(alert), 200


@alerts_bp.put("/<int:alert_id>", responses={200: AlertResponse, 400: ErrorEnvelope, 404: ErrorEnvelope})
def update_alert(path: AlertIdPath, body: AlertUpdatePayload):
    alert = Alert.get_or_none(Alert.id == path.alert_id)
    if alert is None:
        return error_response("Alert not found", "NOT_FOUND", 404)

    if body.status:
        if body.status not in _VALID_STATUSES:
            return error_response(
                f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}",
                "VALIDATION_ERROR",
                400,
            )
        alert.status = body.status
        now = datetime.utcnow()
        if body.status == "acknowledged":
            alert.acknowledged_at = now
            if body.acknowledged_by:
                alert.acknowledged_by = body.acknowledged_by
        elif body.status == "resolved":
            alert.resolved_at = now

    if body.notes:
        timestamp = datetime.utcnow().isoformat()
        new_note = f"[{timestamp}] {body.notes}"
        if alert.notes:
            alert.notes = alert.notes + "\n" + new_note
        else:
            alert.notes = new_note

    alert.save()
    return _serialize_alert(alert), 200
