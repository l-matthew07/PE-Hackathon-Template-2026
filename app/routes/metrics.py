# BRONZE INTEGRATION POINT
# When Bronze structured logging/metrics land, wire real measurements here.
#
# To record a request:
#   from app.routes.metrics import http_requests_total, http_request_duration_seconds, active_requests
#
#   # In @app.before_request:
#   active_requests.inc()
#   g.start_time = time.time()
#
#   # In @app.after_request:
#   active_requests.dec()
#   duration = time.time() - g.start_time
#   http_request_duration_seconds.labels(method=request.method, endpoint=request.endpoint).observe(duration)
#   http_requests_total.labels(method=request.method, endpoint=request.endpoint, status_code=response.status_code).inc()
#
# To record a shortener redirect:
#   from app.routes.metrics import url_shortener_redirects_total
#   url_shortener_redirects_total.labels(status="hit").inc()   # found
#   url_shortener_redirects_total.labels(status="miss").inc()  # 404
#
# To record DB pool connections (e.g. in database.py):
#   from app.routes.metrics import db_pool_connections_active
#   db_pool_connections_active.set(current_connection_count)

from flask import Blueprint
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

metrics_bp = Blueprint("metrics", __name__)

REGISTRY = CollectorRegistry()

# --- Latency ---
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    registry=REGISTRY,
)

# --- Traffic + Errors ---
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    labelnames=["method", "endpoint", "status_code"],
    registry=REGISTRY,
)

# --- Saturation ---
active_requests = Gauge(
    "active_requests",
    "Number of in-flight HTTP requests",
    registry=REGISTRY,
)

# --- App-specific: URL shortener ---
url_shortener_redirects_total = Counter(
    "url_shortener_redirects_total",
    "URL shortener redirect attempts",
    labelnames=["status"],  # "hit" or "miss"
    registry=REGISTRY,
)

# --- App-specific: DB connections ---
db_pool_connections_active = Gauge(
    "db_pool_connections_active",
    "Active database pool connections",
    registry=REGISTRY,
)


@metrics_bp.route("/metrics")
def metrics():
    data = generate_latest(REGISTRY)
    return data, 200, {"Content-Type": CONTENT_TYPE_LATEST}
