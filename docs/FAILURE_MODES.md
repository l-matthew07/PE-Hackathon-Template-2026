# Failure Modes

How this system usually fails, how to spot it, and what to do first.

## Failure types

### Operational

- Container crash/restart loops (web, db, redis, pgbouncer)
- Misconfiguration in environment variables or routing
- Dependency startup ordering and healthcheck failures

### Dependency

- PostgreSQL unavailable or degraded
- PgBouncer unavailable or saturated
- Redis unavailable
- Monitoring/alerting components unavailable (Prometheus, Alertmanager, Loki)

### Data integrity

- Unique key conflicts on create flows
- Invalid or malformed client payloads
- Lock contention causing partial write failures/timeouts

### Performance degradation

- Traffic spikes beyond current concurrency envelope
- Slow queries and DB lock waits
- Cache miss storms that shift load to DB

## Quick matrix

| Failure Mode | Detection Signal | Blast Radius | Typical Root Cause | First Recovery Action |
|---|---|---|---|---|
| ServiceDown alert | up{job="flask_app"} == 0 | Full API impact | app crash, route breakage, dependency down | Restore web health and verify /api/health |
| HighErrorRate alert | 5xx > 5% for 2m | User-visible endpoint errors | dependency fault, bad deploy, data conflicts | Isolate failing endpoint and inspect logs |
| HighLatencyP95 alert | p95 > 2s for 2m | Slow user experience, eventual errors | saturation, lock contention, cache outage | Reduce pressure and inspect DB/pool |
| DB lock contention | p95 rise with normal traffic | Broad slowdown on DB-backed routes | long transaction, table lock | remove lock holder safely |
| Redis outage | Redis errors + latency rise | Degraded performance, not full outage | process crash, network issue | restart Redis and monitor DB pressure |
| Alerting blind spot | Missing alerts/dashboards stale | Delayed incident response | Prometheus/Alertmanager issue | restore monitoring services |

## Detailed modes

### Mode A: web unavailable

Symptoms:

- Health endpoint fails
- ServiceDown alert fires
- nginx returns upstream errors

Detection:

```bash
docker compose ps web nginx
docker compose logs web --tail 200
curl -i http://localhost/api/health
```

First actions:

1. Restart web and confirm healthcheck recovery.
2. If startup fails, verify DB and Redis dependencies.
3. Validate ingress path after recovery.

### Mode B: DB pressure and pool exhaustion

Symptoms:

- Rising latency and in-flight requests
- Timeouts under moderate/high traffic
- Intermittent write failures

Detection:

```bash
docker compose logs pgbouncer --tail 120
docker compose logs db --tail 120
docker compose logs web --tail 120
```

First actions:

1. Reduce incoming pressure (scale or temporary traffic control).
2. Investigate lock holders and long queries.
3. Tune pool and query performance before next load peak.

### Mode C: Redis unavailable (graceful degradation)

Symptoms:

- Redis warnings in logs
- DB pressure increases
- Latency increases without full outage

Detection:

```bash
docker compose ps redis
docker compose logs redis --tail 120
docker compose logs web --tail 120 | grep -i redis
```

First actions:

1. Restore Redis service.
2. Watch p95 and DB saturation until normal baseline returns.
3. Confirm cache behavior normalizes.

### Mode D: data and validation failures

Symptoms:

- 4xx/422 responses for malformed payloads
- Conflict/integrity errors on duplicate writes

Detection:

- Verify request contracts and payload shape.
- Compare with tested graceful error behavior in tests/test_graceful_errors.py.

First actions:

1. Fix caller payload or contract usage.
2. Add idempotency/retry handling where appropriate.
3. Improve validation feedback if repeated client misuse occurs.

## Prevention

- Keep alert rules and runbook aligned.
- Exercise chaos scenarios regularly (high_error_rate, traffic_spike, slow_db).
- Track pre-failure indicators: rising in-flight requests, rising DB pool usage, rising p95.
- Preserve graceful degradation behavior for cache and non-critical dependencies.

## Recovery checklist

After fixes, verify:

1. /api/health returns success through nginx.
2. Error rate returns below warning threshold.
3. p95 latency returns below warning threshold.
4. DB and Redis services are healthy.
5. Dashboards and alerts update in near real time.
