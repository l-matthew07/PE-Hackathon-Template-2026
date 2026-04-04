# Incident Response Runbook — URL Shortener Service

> At 3 AM you are not functional. This document is. Follow the steps exactly.

---

## Severity Classification

| Level | Condition | Response Time |
|---|---|---|
| P1 | Service completely down / error rate > 50% | Immediate — wake someone up |
| P2 | Error rate > 5% **or** p95 latency > 1s for more than 5 minutes | < 15 minutes |
| P3 | Anomalous metric trend, no confirmed user impact | Next working hour |

---

## Service Map

```
Browser → Flask (web:5000) → PostgreSQL (db:5432)
                ↓
         Prometheus (prometheus:9090) scrapes /metrics every 15s
         Node Exporter (node_exporter:9100) reports host CPU/RAM/disk
         Postgres Exporter (postgres_exporter:9187) reports DB internals
                ↓
         Grafana (grafana:3000) visualizes everything
```

---

## Dashboard Access

Open **http://localhost:3000** — no login required (anonymous viewer enabled).

Default home: **Flask App — Incident Response Overview**

### Panel Reference

| Row | Panel | Signal | What it tells you |
|---|---|---|---|
| Golden Signals | Latency P50/P95/P99 | Latency | Is the app slow? Which percentile is spiking? |
| Golden Signals | Traffic — RPS | Traffic | How much load? Which endpoint? Use the Endpoint dropdown to filter. |
| Golden Signals | Errors — 5xx Rate | Errors | What fraction of requests are failing? |
| Golden Signals | Active In-Flight Requests | Saturation | Is the app currently overloaded? |
| Golden Signals | Redirect Hit Rate | App-specific | Are short codes resolving or returning 404? |
| Golden Signals | DB Pool Connections | Saturation | Is the app-level connection pool exhausted? |
| Golden Signals | Request Rate by Status | Traffic + Errors | 2xx vs 4xx vs 5xx breakdown over time |
| Infrastructure | CPU Usage % | Saturation | Is the host overloaded at OS level? |
| Infrastructure | Memory Usage % | Saturation | Is the host running low on RAM? |
| Infrastructure | Disk I/O | Saturation | Is storage a bottleneck? (watch during slow DB) |
| Infrastructure | Network I/O | Traffic | Useful to distinguish CPU-bound vs network-bound slowness |
| PostgreSQL | DB Active Connections | Saturation | Live connections direct from Postgres — more reliable than app metric |
| PostgreSQL | DB Transaction Rate | Traffic | Commits/rollbacks per second — drop = DB bottleneck |
| PostgreSQL | DB Deadlocks/min | Errors | Always a bug — any non-zero value needs investigation |
| SLO | Error Budget Remaining | Errors | How much of the 99.5% SLO budget is left? |
| SLO | SLO Burn Rate | Errors | > 1.0 = burning budget faster than allowed |

### Alert Thresholds

| Metric | Warning | Critical |
|---|---|---|
| Latency P95 | > 250ms | > 1s |
| 5xx Error Rate | > 1% | > 5% |
| Active Requests | > 50 | > 80 |
| App DB Pool Connections | > 15 | > 20 |
| Host CPU % | > 70% | > 90% |
| Host Memory % | > 75% | > 90% |
| Postgres Active Connections | > 15 | > 20 |
| Deadlocks/min | any | any |
| Error Budget Remaining | < 75% | < 25% |

---

## Playbook 1: Service Down (P1)

**Symptom:** Dashboard shows no data, `/health` unreachable, or `up{job="flask_app"} == 0` in Prometheus.

### Step 1 — Confirm the scope (1 min)
```bash
docker compose ps
```
Identify which service shows `exited` or is missing.

### Step 2 — Read crash logs (2 min)
```bash
docker compose logs web --tail=100
docker compose logs db --tail=50
```

### Step 3 — Attempt restart
```bash
docker compose restart web
```
Watch Grafana — the Latency and Traffic panels should show data within 30s.

### Step 4 — If restart fails, full stack restart
```bash
docker compose down && docker compose up -d
```

### Step 5 — Verify recovery
```bash
curl http://localhost:5000/health
# Expected: {"status": "ok"}
```

---

## Playbook 2: High Error Rate (P2)

**Symptom:** Panel "Errors — 5xx Rate" background is red (> 5%).

### Step 1 — Confirm it's sustained (2 min)
Watch the panel for 2 minutes. A single spike < 30s is likely a blip. If it stays red, proceed.

### Step 2 — Identify the offending endpoint (2 min)
Use the **Endpoint** dropdown at the top of the dashboard to filter panel 2 (Traffic — RPS).
Look for the endpoint with a sudden surge in error-coded traffic.

Or query directly in Prometheus Explore (`http://localhost:9090`):
```promql
sum by (endpoint, status_code) (rate(http_requests_total{status_code=~"5.."}[5m]))
```

### Step 3 — Read the logs (3 min)
```bash
docker compose logs web --since=10m | grep -i error
```
Find the first ERROR line that preceded the alert. Copy the traceback.

### Step 4 — Check if DB is the cause
If the error message mentions a DB connection or query failure, check:
```promql
pg_stat_activity_count{datname="hackathon_db"}
```
If connections are at or above 20, DB pool is exhausted → follow Playbook 4.

### Step 5 — Check for a bad deploy
```bash
git log --oneline -5
```
If a recent commit correlates with the alert start time, revert it:
```bash
git revert HEAD
docker compose build web && docker compose up -d web
```

### Step 6 — Restart as last resort
```bash
docker compose restart web
```

---

## Playbook 3: High Latency (P2)

**Symptom:** Panel 1 P95 line is red (> 1s) or trending upward for > 5 minutes.

### Step 1 — Check CPU and Memory (1 min)
Open the **Infrastructure** row. If CPU > 90%, the host is overloaded — high latency is a symptom of saturation, not a DB issue.

### Step 2 — Check if latency is DB-driven (2 min)
Open the **PostgreSQL** row. If "DB Active Connections" is spiking, or "DB Transaction Rate" is dropping while latency climbs, the DB is the bottleneck.

Inspect running queries:
```bash
docker compose exec db psql -U postgres hackathon_db \
  -c "SELECT pid, state, query, query_start FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;"
```

### Step 3 — Kill long-running queries
If you see queries running for more than 30s:
```bash
docker compose exec db psql -U postgres hackathon_db \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '30 seconds';"
```

### Step 4 — Restart web if CPU is the cause
```bash
docker compose restart web
```

---

## Playbook 4: DB Connection Exhaustion (P2)

**Symptom:** "DB Active Connections" stat is red, app may be throwing connection errors in logs.

### Step 1 — Confirm connection count
```bash
docker compose exec db psql -U postgres hackathon_db \
  -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```

### Step 2 — Find stuck connections
```bash
docker compose exec db psql -U postgres hackathon_db \
  -c "SELECT pid, state, query_start, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;"
```

### Step 3 — Restart web to release app connections
```bash
docker compose restart web
```
This drops all pooled connections from the app side. Confirm count drops.

### Step 4 — Terminate stuck server-side connections
If connections remain after restarting web:
```bash
docker compose exec db psql -U postgres hackathon_db \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction';"
```

---

## Playbook 5: High Saturation — CPU or Memory Spike (P2/P3)

**Symptom:** Infrastructure row — CPU % or Memory % panels are red.

### Step 1 — Identify the process
CPU spike:
```bash
docker stats --no-stream
```
Look for the container consuming the most CPU.

Memory spike:
```bash
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}"
```

### Step 2 — Correlate with traffic
Check panel 2 (Traffic — RPS). If traffic is elevated, the load is expected.
If traffic is normal but CPU is high, look for a runaway loop or large query.

### Step 3 — Restart the offending container
```bash
docker compose restart web   # or db, prometheus, etc.
```

---

## Playbook 6: DB Deadlocks (P3)

**Symptom:** "DB Deadlocks/min" panel shows any non-zero value.

Deadlocks are always a bug — two transactions are acquiring locks in conflicting order.

### Step 1 — Confirm and timestamp
Note when the deadlocks started. Check git log for any recent changes to DB write logic.

### Step 2 — Read Postgres logs
```bash
docker compose logs db --since=30m | grep -i deadlock
```

### Step 3 — File a bug
Deadlocks rarely need immediate rollback. File a bug with the timestamp, query text, and any relevant deploy. Fix in code — not in prod.

---

## Quick Reference

| Symptom | First panel to check | Likely cause | Fix |
|---|---|---|---|
| No data anywhere | Prometheus targets page | Service down | `docker compose ps` |
| Latency spiking | DB Active Connections | DB bottleneck | Kill long queries, restart web |
| Error rate > 5% | Traffic by endpoint | Bad deploy or DB down | Check logs, maybe revert |
| CPU > 90% | Traffic RPS | Traffic spike or loop | Restart web |
| Memory climbing | Memory % trend | Memory leak | Restart web, file bug |
| Deadlocks | DB Deadlocks/min | Code bug in write path | File bug, check recent deploy |

---

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

# Open Grafana dashboard
open http://localhost:3000

# Check if /metrics is returning data
curl http://localhost:5000/metrics

# Rebuild after code changes
docker compose build web && docker compose up -d web

# Run the chaos demo (Sherlock Mode)
uv run scripts/chaos.py high_error_rate
uv run scripts/chaos.py traffic_spike
uv run scripts/chaos.py slow_db
```

---

## Integration Notes

- **Bronze** wires real timing/counts into the metric counters and histograms — all Golden Signal panels auto-populate with real data once complete.
- **Silver** adds Alertmanager alerts — the thresholds table above becomes automated Discord pings.
- The Infrastructure and PostgreSQL rows are live **now** — node_exporter and postgres_exporter are running and require no further wiring.
