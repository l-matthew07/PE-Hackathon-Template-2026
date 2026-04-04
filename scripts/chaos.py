"""
Chaos engineering script — simulate real failure modes for the Sherlock Mode demo.

Usage:
    uv run scripts/chaos.py <scenario>

Scenarios:
    high_error_rate   Send 200 bad requests to /shorten — watch error rate spike
    traffic_spike     20 concurrent threads flood the app — watch RPS and latency spike
    slow_db           Hold an exclusive lock on the urls table for 60s — watch DB panels

Demo flow:
    1. Open Grafana at http://localhost:3000 — all panels green
    2. Run a scenario in a second terminal
    3. Point to the dashboard and narrate what changed and why
    4. Use Prometheus Explore (http://localhost:9090) or Grafana Explore to drill in
"""

import json
import sys
import threading
import time
from http.client import HTTPConnection
from urllib.error import URLError
from urllib.request import Request, urlopen

BASE_URL = "http://localhost:5000"


def _post(path: str, data: dict) -> int | None:
    body = json.dumps(data).encode()
    req = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=5) as r:
            return r.status
    except Exception:
        return None


def _get(path: str) -> int | None:
    try:
        with urlopen(f"{BASE_URL}{path}", timeout=5) as r:
            return r.status
    except Exception:
        return None


def high_error_rate() -> None:
    """
    Sends 200 requests with invalid URLs to /shorten.
    The shortener validates URLs, so each request returns a 4xx/5xx.
    Watch: panel 3 (Errors — 5xx Rate) background turns red.
    Diagnosis path: error rate panel → endpoint filter → logs for traceback.
    """
    print("[chaos] Starting high_error_rate — sending 200 invalid /shorten requests")
    print("[chaos] Watch: Grafana panel 3 (Errors — 5xx Rate)")
    errors = 0
    for i in range(200):
        status = _post("/shorten", {"url": "not-a-valid-url"})
        if status and status >= 400:
            errors += 1
        time.sleep(0.05)
    print(f"[chaos] Done. {errors}/200 requests returned error status.")
    print("[chaos] In Grafana, filter panel 2 by endpoint='/shorten' to confirm source.")


def traffic_spike() -> None:
    """
    Spins up 20 threads each firing 50 GET /health requests.
    Watch: panel 2 (Traffic — Requests per Second) spikes 10-20x.
    Also watch: panel 4 (Active In-Flight Requests) gauge climb.
    """
    print("[chaos] Starting traffic_spike — 20 threads × 50 requests to /health")
    print("[chaos] Watch: Grafana panel 2 (Traffic — Requests per Second)")

    def worker() -> None:
        for _ in range(50):
            _get("/health")
            time.sleep(0.01)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print("[chaos] Done. RPS should have spiked on panel 2 and is now recovering.")


def slow_db(duration_seconds: int = 60) -> None:
    """
    Opens a Postgres connection and holds an EXCLUSIVE lock on the urls table.
    Any web request that touches urls (redirect lookups, shortens) will hang
    waiting for the lock, causing latency to skyrocket.
    Watch: panel 1 (Latency P95/P99) climb, then panel 4 (Active In-Flight) climb.
    Postgres exporter will also show active connections spiking.
    """
    print(f"[chaos] Starting slow_db — holding EXCLUSIVE lock on urls for {duration_seconds}s")
    print("[chaos] Watch: Grafana panel 1 (Latency P50/P95/P99) and Infrastructure > DB panels")
    try:
        import psycopg2
    except ImportError:
        print("[chaos] psycopg2 not found. Run: uv add psycopg2-binary")
        sys.exit(1)

    try:
        conn = psycopg2.connect(
            dbname="hackathon_db",
            user="postgres",
            password="postgres",
            host="localhost",
            port=5432,
        )
        cur = conn.cursor()
        cur.execute("BEGIN;")
        cur.execute("LOCK TABLE urls IN EXCLUSIVE MODE;")
        print(f"[chaos] Lock acquired. Sleeping {duration_seconds}s. Ctrl+C to release early.")
        try:
            time.sleep(duration_seconds)
        except KeyboardInterrupt:
            print("\n[chaos] Interrupted — releasing lock early.")
        conn.rollback()
        conn.close()
        print("[chaos] Lock released. Latency should recover within ~15s.")
    except Exception as e:
        print(f"[chaos] DB connection failed: {e}")
        print("[chaos] Make sure docker compose is up and DB is on localhost:5432")
        sys.exit(1)


SCENARIOS = {
    "high_error_rate": high_error_rate,
    "traffic_spike": traffic_spike,
    "slow_db": slow_db,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in SCENARIOS:
        print("Usage: uv run scripts/chaos.py <scenario>")
        print(f"Scenarios: {', '.join(SCENARIOS)}")
        sys.exit(1)
    SCENARIOS[sys.argv[1]]()
