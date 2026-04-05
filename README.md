# MLH PE Hackathon 2026 — URL Shortener

A URL shortener service with a full incident response observability, reliability, and scalability stack built for the MLH PE Hackathon.

**Stack:** Flask · Peewee ORM · PostgreSQL · Redis · nginx · Prometheus · Grafana · Loki · Alertmanager · Discord · uv

**Live dashboard:** https://165.245.232.106/admin/

---

## What We Built

### Tier 1 — Bronze: The Watchtower
- Structured JSON logging with timestamps and log levels
- `/metrics` endpoint exposing Prometheus metrics (request counts, latency histograms, active requests, redirect hit/miss)

### Tier 2 — Silver: The Alarm
- Alertmanager configured with `ServiceDown` and `HighErrorRate` alert rules
- Discord notifications via a custom relay service — alerts fire within 5 minutes of failure
- Acknowledgement and escalation bot

### Tier 3 — Gold: The Command Center
- Grafana dashboard with 4 Golden Signals (Latency, Traffic, Errors, Saturation) + Infrastructure + PostgreSQL + SLO rows
- Prometheus recording rules for p95/p99 latency, error budget, and burn rate
- Runbook (`RUNBOOK.md`) with 6 playbooks, panel reference, and Sherlock Mode incident walkthrough
- Chaos engineering scripts for live demo (`scripts/chaos.py`)

---

## Quick Start

### Docker

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Run migrations
docker compose --profile setup run --rm migrate

# 3. Start everything
docker compose up -d

# 4. Verify
curl http://localhost/health
# → {"status": "ok"}

# 5. Open dashboard
open http://localhost/admin/
```

### Local development

```bash
# Install dependencies
uv sync

# Run the server
uv run run.py

# Verify
curl http://localhost:5000/health
```

---

## Services

| Service | URL | Description |
|---|---|---|
| App (via nginx) | http://localhost/ | URL shortener UI + API |
| Grafana | http://localhost/admin/ | Observability dashboard |
| Prometheus | http://localhost:9090 | Metrics + alerting |
| Alertmanager | http://localhost:9093 | Alert routing |

---

## API Endpoints

```bash
# Shorten a URL
curl -X POST http://localhost/shorten \
    -H "Content-Type: application/json" \
    -d '{"url": "https://example.com/some/long/path"}'
# → {"short_code": "a1B2c3", "short_url": "http://localhost/a1B2c3", ...}

# Redirect
curl -i http://localhost/a1B2c3

# Health check
curl http://localhost/health

# Metrics
curl http://localhost/metrics

# API docs
open http://localhost/docs
```

---

## Chaos Demo (Sherlock Mode)

Simulate incidents to demonstrate the dashboard and alerting:

```bash
# Spike the error rate — watch Error Rate % panel turn red
uv run scripts/chaos.py high_error_rate

# Flood traffic — watch RPS and In-Flight gauges spike
uv run scripts/chaos.py traffic_spike

# Lock the DB for 60s — watch latency climb and PostgreSQL panels spike
uv run scripts/chaos.py slow_db
```

See `RUNBOOK.md` for the full Sherlock Mode walkthrough.

---

## Scaling

```bash
# Scale to 4 web replicas
docker compose up -d --scale web=4

# Load test with k6
k6 run scripts/k6-test.js -e BASE_URL=http://localhost -e VUS=200 -e DURATION=3m
```

---

## Migrations

```bash
# Apply all pending migrations
uv run scripts/migrate.py up

# Roll back the latest migration
uv run scripts/migrate.py down

# Create a new migration
uv run scripts/migrate.py create add_some_change
```

---

## Project Structure

```
├── app/
│   ├── models/          # Peewee ORM models
│   ├── routes/          # Flask blueprints (shortener, metrics, health)
│   ├── services/        # Business logic
│   └── cache.py         # Redis cache helpers
├── grafana/             # Grafana provisioning (dashboard JSON, datasources)
├── prometheus/          # prometheus.yml + recording rules
├── monitoring/          # Alertmanager config + Discord relay + alert rules
├── scripts/             # chaos.py, migrate.py, k6 load test, deploy script
├── migrations/          # peewee-migrate migration files
├── RUNBOOK.md           # Incident response playbooks
└── docker-compose.yml
```

---

## Deploying to the Server

```bash
# Push changes
git add . && git commit -m "your message" && git push origin main

# Deploy on the server
ssh -i /tmp/hackathon_key root@165.245.232.106
cd /root/repo && git pull origin main && docker compose up -d --force-recreate grafana
```
