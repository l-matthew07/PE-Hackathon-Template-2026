# Architecture Decision Log

Why we built it this way.

## Entry: PgBouncer Between App and PostgreSQL

Context: Three web replicas with threaded workers can burst DB connections.

Decision: Put PgBouncer in front of PostgreSQL (transaction mode).

Tradeoff: One more service to run and monitor.

Consequence: Fewer DB connection storms during traffic spikes.

## Entry: Redis as a Performance Optimization, Not a Hard Dependency

Context: Caching helps a lot, but we did not want cache failures to become outages.

Decision: Redis cache calls fail open and return misses on errors.

Tradeoff: Requests get slower while Redis is unhealthy.

Consequence: API stays up, performance degrades instead of hard failing.

## Entry: Three Web Replicas Behind nginx

Context: A single web instance is too fragile during spikes and restarts.

Decision: Run three web replicas and balance with nginx.

Tradeoff: Slightly higher runtime cost.

Consequence: Better uptime and more headroom.

## Entry: Prometheus + Grafana + Alertmanager + Loki

Context: On-call debugging is faster with metrics and logs in one place.

Decision: Use Prometheus, Grafana, Alertmanager, and Loki together.

Tradeoff: Bigger stack to maintain.

Consequence: Faster diagnosis and cleaner incident timelines.

## Entry: Keep Event Records Decoupled from URL FK Deletes

Context: We want event history even if URLs are deleted.

Decision: Keep event url_id as a plain integer, not an enforced FK.

Tradeoff: We lose some relational guarantees.

Consequence: Historical event records survive URL deletion.
