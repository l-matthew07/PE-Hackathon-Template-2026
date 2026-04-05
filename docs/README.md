# Documentation Index

Quick links for ops and architecture docs.

## Contents

- [Troubleshooting Guide](./TROUBLESHOOTING_GUIDE.md)
- [Architecture Decision Log](./ADL.md)
- [Max Capacity Plan](./CAPACITY_LIMITS.md)
- [Failure Modes](./FAILURE_MODES.md)

## How to Use

- Start with the troubleshooting guide during incidents.
- Read the decision log for architecture rationale.
- Use the capacity plan before load tests or scaling.
- Use failure modes for risk reviews and game days.

## Canonical References

Source-of-truth files:

- RUNBOOK.md for incident playbooks
- monitoring/alert_rules.yml for alert definitions and thresholds
- docker-compose.yml for runtime topology and service config
- scripts/chaos.py for reproducible failure simulations
