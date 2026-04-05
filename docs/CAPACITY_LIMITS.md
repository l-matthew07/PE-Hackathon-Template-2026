# Max Capacity Plan

Where this stack will bottleneck first, and what to do about it.

## Capacity snapshot

From docker-compose.yml:

- web replicas: 3
- gunicorn workers per replica: 2
- threads per worker: 12
- rough concurrent handlers: 3 x 2 x 12 = 72

Database side:

- app pool: DATABASE_POOL_MAX_CONNECTIONS=16 per replica
- theoretical app-side max open DB conns: 3 x 16 = 48
- PgBouncer DEFAULT_POOL_SIZE=30, MAX_CLIENT_CONN=300

Bottom line: DB connection pressure is likely your first hard limit.

## Bottleneck inventory

| Layer | Bottleneck | Saturation Signal | User Impact | Immediate Action |
|---|---|---|---|---|
| App runtime | Thread/worker saturation | Rising in-flight requests, queueing | Higher latency, timeouts | Scale web replicas |
| DB access | App pool + PgBouncer pool pressure | p95 latency rises with DB active connections | Slow writes/reads, 5xx risk | Reduce load, tune pool, optimize queries |
| PostgreSQL | Locks/contention and I/O | Lock waits, long queries, slow commits | Broad endpoint slowdown | Find blocking query, terminate lock holder if needed |
| Redis | Single-instance cache dependency | Cache misses rise, Redis errors in logs | More DB load, latency increase | Restart Redis, protect DB from surge |
| nginx | Upstream pressure | Upstream timeouts/5xx | Partial outage symptoms | Add replicas, inspect upstream health |
| Observability | Metrics/log storage growth | Prometheus/Loki storage pressure | Reduced visibility | Trim retention, add storage |

## Failure patterns

### Traffic spike

- Early: RPS and in-flight requests jump.
- Mid: DB pool usage climbs, latency rises.
- Late: 5xx crosses alert threshold.

Do this:

1. Scale web replicas.
2. Verify DB pool utilization and lock contention.
3. Restore cache health if degraded.
4. Shed non-critical load if needed.

### Slow DB or lock contention

- Early: p95 rises while traffic is stable.
- Mid: queueing at pool/pgbouncer.
- Late: timeout-driven 5xx.

Do this:

1. Identify lock holders and long-running queries.
2. Kill or rollback blocking transaction if safe.
3. Reduce write pressure temporarily.
4. Apply query/index fixes.

### Cache outage

- Early: Redis warnings and worse cache hit behavior.
- Mid: DB QPS and pool pressure rise.
- Late: latency and error-rate alerts fire.

Do this:

1. Recover Redis service.
2. Protect DB with temporary scaling and traffic control.
3. Invalidate stale keys carefully once cache is back.

## Guardrails

- Keep p95 latency comfortably below the 2s alert threshold.
- Keep sustained 5xx well below 5% warning threshold.
- Treat persistent DB pool saturation as a hard warning sign.
- Watch for coupled degradation: cache miss increase plus DB pool pressure.

## Scaling plan

### Start horizontal

- Scale web replicas for fast relief.
- Keep nginx upstream balanced and healthy.
- Consider read replicas for heavy read scenarios.

### Then tune

- Tune app DB pool and PgBouncer limits together.
- Revisit gunicorn worker/thread mix based on CPU and blocking profile.
- Optimize expensive queries and add indexes where justified.

### Resilience upgrades

- Add Redis HA (sentinel/cluster) for stronger cache availability.
- Add circuit-breaking or request shedding for dependency failures.
- Define SLO-backed autoscaling thresholds.

## Validate with load and chaos

Run these:

- uv run scripts/chaos.py traffic_spike
- uv run scripts/chaos.py slow_db
- k6 run scripts/k6-test.js

For each run, record:

- max sustained RPS
- p95/p99 latency
- error rate
- DB pool behavior
- recovery time after pressure release
