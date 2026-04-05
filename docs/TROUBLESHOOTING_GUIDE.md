# Troubleshooting Guide

Use this when something looks wrong and you need a fast answer.

## First 2 minutes

```bash
docker compose ps
curl -i http://localhost/api/health
docker compose logs web --tail 120
```

If the dashboard is red, follow RUNBOOK.md first. Come back here for deeper checks.

## Alerts

Alert rules live in monitoring/alert_rules.yml.

### ServiceDown

- Means Prometheus cannot scrape flask_app for 1 minute.

```bash
docker compose ps web nginx prometheus
docker compose logs web --tail 200
docker compose logs nginx --tail 100
curl -i http://localhost/api/health
```

Usual causes: crashed web container, DB/Redis down, bad nginx upstream path.

### HighErrorRate

- Means 5xx is above 5% for 2 minutes.

```bash
docker compose logs web --tail 200 | grep -E "ERROR|Traceback|IntegrityError"
curl -i http://localhost/api/health
```

Usual causes: bad payloads, dependency failures, write conflicts.

### HighLatencyP95

- Means p95 is above 2s for 2 minutes.

```bash
docker compose logs web --tail 200
docker compose logs pgbouncer --tail 120
docker compose ps db redis pgbouncer
```

Usual causes: DB pool pressure, DB lock contention, Redis outage (more DB traffic).

## Common symptoms

### API is up but slow

1. Check p95 and in-flight requests in Grafana.
2. Check DB pool and pgbouncer pressure.
3. Check Redis health.

### Lots of 422/4xx

1. Verify request shape against OpenAPI docs.
2. Confirm body is valid JSON object.
3. Confirm IDs and required fields.

Expected behavior:

- malformed JSON to /urls -> 422
- null body to /urls -> 422
- empty original_url -> 400
- unknown route -> JSON 404

### Writes fail intermittently

1. Check integrity conflicts in logs.
2. Check DB lock waits.
3. Check pgbouncer queue pressure.

## Dependency checks

### PostgreSQL and PgBouncer

```bash
docker compose ps db pgbouncer
docker compose logs db --tail 120
docker compose logs pgbouncer --tail 120
```

### Redis

```bash
docker compose ps redis
docker compose logs redis --tail 120
```

Redis is fail-open in this app: cache errors should degrade performance, not crash requests.

### Prometheus and Alertmanager

```bash
docker compose ps prometheus alertmanager
docker compose logs prometheus --tail 120
docker compose logs alertmanager --tail 120
```

## Recovery checklist

1. Restart the smallest thing first (web, then redis/pgbouncer, then db).
2. Re-test /api/health and one write (POST /urls).
3. Watch error rate and p95 for at least 5 minutes.

## Useful commands

```bash
docker compose logs web -f
docker compose up -d --scale web=4
curl -s http://localhost/api/metrics | head
open http://localhost:9090/targets
```
