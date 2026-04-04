from collections.abc import Callable

from flask import Blueprint, jsonify, request

from app.lib.api import error_response
from app.services.errors import ServiceError


def register_bulk_load_endpoint(
    blueprint: Blueprint,
    loader: Callable[[str], int],
    *,
    route: str = "/bulk",
    default_file: str,
    success_status: int = 200,
) -> None:
    endpoint_name = f"{blueprint.name}_bulk_load"

    def _bulk_load_handler():
        payload = request.get_json(silent=True) or {}
        filename = str(payload.get("file") or default_file).strip() or default_file
        requested_count = payload.get("row_count")

        try:
            loaded_count = loader(filename)
        except ServiceError as exc:
            return error_response(exc.message, exc.code, exc.status, details=exc.details)

        return (
            jsonify({"file": filename, "row_count": requested_count, "loaded": loaded_count}),
            success_status,
        )

    blueprint.add_url_rule(route, endpoint_name, _bulk_load_handler, methods=["POST"])