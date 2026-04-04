# Incident Response Runbook — URL Shortener Service

> At 3 AM you are not functional. This document is. Follow the steps exactly.

## Service Map

```
Browser → Flask (web:5000) → PostgreSQL (db:5432)
                ↓
         Prometheus (prometheus:9090) scrapes /metrics every 15s
                ↓
         Grafana (grafana:3000) visualizes everything
```

## Dashboard Access

Open **http://localhost:3000** — no login required (anonymous viewer enabled).

Default home: **Flask App — Incident Response Overview**

| Panel | Signal | What it tells you |
|---|---|---|
| Latency P50/P95/P99 | Latency | Is the app slow? Which percentile is spiking? |
| Requests per Second | Traffic | How much load is there? Which endpoint? |
| 5xx Error Rate | Errors | What fraction of requests are failing? |
| Active In-Flight Requests | Saturation | Is the app overloaded right now? |
| Redirect Hit Rate | App-specific | Are short codes resolving or returning 404? |
| DB Pool Connections | Saturation | Is the database connection pool exhausted? |
| Request Rate by Status | Traffic+Errors | Breakdown of 2xx vs 4xx vs 5xx over time |

## Alert Thresholds (Manual — Pre-Silver)

| Metric | Warning | Critical |
|---|---|---|
| Latency P95 | > 250ms | > 1s |
| 5xx Error Rate | > 1% | > 5% |
| Active Requests | > 50 | > 80 |
| DB Connections | > 15 | > 20 |

---

## Runbook Procedures

### SERVICE DOWN

**Symptom:** Dashboard shows no data, `/health` unreachable, or `up{job="flask_app"} == 0` in Prometheus.

1. Check which service is down: `docker compose ps`
2. Read the last 50 log lines: `docker compose logs <service> --tail=50`
3. Restart the service: `docker compose restart <service>`
4. If that fails, full restart: `docker compose down && docker compose up -d`
5. Verify health: `curl http://localhost:5000/health`

---

### HIGH LATENCY (P95 > 1s)

**Symptom:** Panel 1 P95 line is red or trending up.

1. Check **which endpoint** is slow — use panel 1 filtered by endpoint label.
2. Check **DB connections** (panel 6) — if high, DB is the bottleneck.
3. Read DB slow query logs: `docker compose logs db --tail=100`
4. Read web logs: `docker compose logs web --since=5m`
5. If DB is the problem, restart it: `docker compose restart db`, then `docker compose restart web`
6. If web is the problem, scale or restart: `docker compose restart web`

---

### HIGH ERROR RATE (5xx > 5%)

**Symptom:** Panel 3 background is red.

1. Note the **start time** on panel 3 — when did it begin?
2. Check what changed at that time: `git log --since="30 minutes ago"`
3. Read error logs: `docker compose logs web --since=10m | grep ERROR`
4. Check if DB is reachable: `docker compose exec web python -c "from app.database import db; db.connect(); print('ok')"`
5. If DB is down: `docker compose restart db && docker compose restart web`
6. If it's a code bug, revert: `git revert HEAD && docker compose restart web`

---

### DB CONNECTION EXHAUSTION (DB Connections > 20)

**Symptom:** Panel 6 background is red, app may be throwing connection errors.

1. Check current connections directly:
   ```
   docker compose exec db psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
   ```
2. Identify which queries are open:
   ```
   docker compose exec db psql -U postgres -c "SELECT pid, state, query, query_start FROM pg_stat_activity WHERE state != 'idle';"
   ```
3. Restart web to release all connections: `docker compose restart web`
4. If connections are still stuck, terminate them:
   ```
   docker compose exec db psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction';"
   ```

---

### HIGH SATURATION (Active Requests > 80)

**Symptom:** Panel 4 gauge is red.

1. Check request rate (panel 2) — is traffic actually high or are requests hanging?
2. If traffic is normal but active count is high → requests are **hanging**, likely DB wait.
3. Follow the DB Connection Exhaustion procedure above.
4. If traffic is genuinely high → you're overloaded. Identify the hot endpoint on panel 2.

---

## Bronze/Silver Integration Notes

Once your teammates complete Bronze and Silver:

- **Bronze** wires real timing/counts into `http_request_duration_seconds` and `http_requests_total` — all panels auto-populate with real data.
- **Silver** adds Alertmanager alerts — the thresholds table above becomes automated Discord pings.
- Update this runbook to reference real alert names once Silver ships.

## Useful Commands

```bash
# View live logs
docker compose logs -f web

# Check all service health
docker compose ps

# Restart one service
docker compose restart web

# Full stack restart
docker compose down && docker compose up -d

# Open Prometheus expression browser
open http://localhost:9090

# Check if /metrics is returning data
curl http://localhost:5000/metrics

# Rebuild after code changes
docker compose build web && docker compose up -d web
```
