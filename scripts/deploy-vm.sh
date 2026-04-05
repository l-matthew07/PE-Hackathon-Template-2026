#!/usr/bin/env bash
set -euo pipefail

git fetch --all --prune
git checkout main
git reset --hard origin/main

if [[ ! -f .env ]]; then
  echo ".env not found in $(pwd). Create it before deployment."
  exit 1
fi

#docker compose --profile setup run --rm migrate
#docker compose run --rm --no-deps web uv run scripts/seed.py

docker compose up -d --remove-orphans

docker image prune -f || true

docker compose ps
curl -fsS http://localhost/api/health

echo "Deployment completed successfully"
