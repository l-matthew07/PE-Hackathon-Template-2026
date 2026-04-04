from typing import Any
from flask import jsonify


def error_response(
    message: str,
    code: str,
    status: int,
    details: dict[str, Any] | None = None,
):
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status


def list_response(items: list[dict], page: int, per_page: int):
    return (
        jsonify(
            {
                "data": items,
                "meta": {
                    "page": page,
                    "per_page": per_page,
                    "count": len(items),
                },
            }
        ),
        200,
    )
