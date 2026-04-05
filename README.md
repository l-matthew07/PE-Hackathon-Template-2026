# MLH PE Hackathon 2026 — URL Shortener

A URL shortener with a full incident response, observability, and reliability stack — because shortening URLs is easy, keeping them up at 3am is not.

**Landing**: http://wealways.online

**Live dashboard:** http://wealways.online/dashboard

---

## 🌟 Features!

| Feature | Description |
|---|---|
| Structured Logging | JSON logs with timestamps, log levels, and request context |
| Prometheus Metrics | Request counts, latency histograms, active requests, redirect hit/miss |
| Grafana Dashboard | 4 Golden Signals (Latency, Traffic, Errors, Saturation) + Infrastructure + PostgreSQL rows |
| Alerting | `ServiceDown`, `HighErrorRate`, `HighLatencyP95` rules with Discord notifications |
| Incident Runbook | Playbooks for every alert, panel reference, severity guide |
| Chaos Scripts | Simulate high error rate, traffic spikes, and slow DB for live demos |

---

## 🚀 Local Setup

### Prerequisites
- Docker + Docker Compose
- `uv` for local dev

### Setup

```bash
cp .env.example .env
docker compose --profile setup run --rm migrate
docker compose up -d
```

Verify: `curl http://localhost/health` → `{"status": "ok"}`

---

## API Usage

1. **Shorten a URL** — `POST /shorten` with `{"url": "https://example.com/..."}`
2. **Redirect** — `GET /<short_code>`
3. **Dashboard** — http://localhost/admin/
4. **API docs** — http://localhost/docs
5. **Chaos demo** — `uv run scripts/chaos.py high_error_rate`

---

## Hosting config

- API is hosted on /api
- Grafana on /dashboard
- Prometheus on /prometheus
- Landing on /

---

## Tech Stack

| Component | Technologies |
|---|---|
| App | Flask, Peewee ORM, PostgreSQL, Redis |
| Infrastructure | nginx, Docker Compose, gunicorn |
| Observability | Prometheus, Grafana, Loki, Alertmanager |
| Notifications | Discord webhook relay |
