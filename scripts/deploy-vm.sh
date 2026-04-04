#!/usr/bin/env bash
set -euo pipefail

git fetch --all --prune
git checkout main
git pull --ff-only origin main

if [[ ! -f .env ]]; then
  echo ".env not found in $(pwd). Create it before deployment."
  exit 1
fi

docker compose pull || true
docker compose build --pull
docker compose up -d db redis
docker compose --profile setup run --rm migrate
#docker compose run --rm --no-deps web uv run scripts/seed.py

docker compose up -d --remove-orphans --scale web=2 web nginx prometheus alertmanager discord-relay

docker image prune -f || true

docker compose ps
curl -fsS http://localhost/health

echo "Deployment completed successfully"
