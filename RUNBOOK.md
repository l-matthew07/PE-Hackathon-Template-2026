# Incident Runbook — URL Shortener

> This runbook exists so that at 3 AM, when you are not thinking clearly, you still know what to do.

---

## Alert: Service Down

**What it means:** Prometheus cannot reach the Flask app. The service is completely unreachable.

**Steps:**
1. Check if containers are running:
   ```bash
   docker compose ps
   ```
   Look for `web-1`, `web-2` — they should say `Up (healthy)`.

2. If a container is down, restart it:
   ```bash
   docker compose restart web
   ```

3. Check logs for crash reason:
   ```bash
   docker compose logs web --tail 50
   ```
   Common causes: missing environment variable, database connection failed, port conflict.

4. If the database is down:
   ```bash
   docker compose restart db
   docker compose restart web
   ```

5. Verify recovery: open Grafana → Service Health panel should turn green within 1 minute.

---

## Alert: High Error Rate

**What it means:** More than 5% of requests are returning 5xx errors over the last 2 minutes.

**Steps:**
1. Check which endpoint is failing — open Grafana → **Traffic — Requests per Second** panel, filter by `status_code=~"5.."`.

2. Check recent logs:
   ```bash
   docker compose logs web --tail 100 | grep "ERROR"
   ```

3. Common causes and fixes:

   | Symptom | Cause | Fix |
   |---|---|---|
   | `relation does not exist` | DB tables missing | `docker compose restart web` |
   | `connection refused` | Redis or DB down | `docker compose restart redis db` |
   | `IntegrityError` | Duplicate data | Check the request payload |
   | All 5xx on one endpoint | Code bug | Check recent git commits |

4. If errors started after a deploy:
   ```bash
   git log --oneline -5
   git revert HEAD
   git push origin main
   ```

5. Verify recovery: Grafana → Error Rate % should drop below 5%.

---

## Alert: High Latency P95

**What it means:** 95% of requests are taking longer than 2 seconds for at least 2 minutes.

**Steps:**
1. Open Grafana → **Latency — Distribution Heatmap** — identify which time the slowdown started.

2. Check active in-flight requests — Grafana → **Saturation — Active In-Flight Requests**. If this is very high, the app is overloaded.

3. Check DB connections — Grafana → **Saturation — DB Pool Connections**. If maxed out, queries are queuing.

4. Check if Redis is up (cache misses = every request hits the DB):
   ```bash
   docker compose ps redis
   ```
   If Redis is down: `docker compose restart redis`

5. If the app is just overloaded, scale up:
   ```bash
   docker compose up --scale web=4 -d
   ```

6. Verify recovery: Grafana → p95 Latency should drop below 2 seconds.

---

## General: App is slow but no alert fired

1. Open Grafana dashboard
2. Check **Traffic — Request Rate by Status Code** — is anything unusual?
3. Check **Saturation — DB Pool Connections** — are connections maxed?
4. Check **CPU %** and **Memory %** — is the host struggling?
5. Check logs: `docker compose logs web --tail 50`

---

## What each Grafana panel tells you

| Panel | What to look for |
|---|---|
| Service Health | All green = good. Any red = something is down |
| Error Rate % | Should be near 0. Spikes = something is broken |
| p95 Latency | Should be under 500ms normally. Over 2s = slowdown |
| CPU % | Over 90% sustained = app is struggling |
| DB Connections | Maxed out = queries are queuing, latency will spike |
| Active In-Flight Requests | Sudden jump = traffic spike or requests hanging |
| Traffic — Requests per Second | Sudden drop to 0 = app is down |
| URL Redirect Hit Rate | Low hit rate = cache not working or bad short codes |

---

## Severity guide

| Situation | Severity | Action |
|---|---|---|
| App completely down | Critical | Wake someone up immediately |
| Error rate > 5% for 2+ min | Warning | Investigate within 15 minutes |
| p95 latency > 2s for 2+ min | Warning | Investigate within 15 minutes |
| Single endpoint erroring | Low | Check logs, probably a bad request |
| Dashboard shows no data | Low | Check Prometheus targets at `localhost:9090/targets` |

---

## Useful commands

```bash
# See all container statuses
docker compose ps

# Restart everything
docker compose restart

# Tail logs from the app
docker compose logs web -f

# Check metrics endpoint directly
curl http://localhost/metrics | grep http_requests_total

# Manually fire a test alert
curl -s -X POST http://localhost:9093/api/v2/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"ServiceDown","severity":"critical"},"annotations":{"summary":"Test alert"}}]'
```
