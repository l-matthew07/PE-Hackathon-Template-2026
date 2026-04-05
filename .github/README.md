# CI/CD Quick Guide

This folder contains GitHub Actions workflows for testing, deploys, and rollbacks.

## What runs in CI/CD

- `.github/workflows/test.yml`
  - Runs on:
    - Push to `main` and `logs`
    - Pull request to `main`
  - Jobs:
    - `test`: installs Python via `uv`, runs `pytest` with coverage, uploads coverage artifact
    - `verify-docker-compose`: validates compose config with `docker compose up --dry-run`
    - `deploy`: runs only for pushes to `main` after test jobs pass

- `.github/workflows/deploy.yml`
  - Manual deploy (`workflow_dispatch`) of latest `main`.

- `.github/workflows/rollback.yml`
  - Manual rollback (`workflow_dispatch`) to previous commit (`HEAD^`) on the VM, then redeploys.

- `.github/workflows/rollback-to-ref.yml`
  - Manual rollback (`workflow_dispatch`) to a specific commit/tag/branch with confirmation input (`ROLLBACK`), then redeploys.

## Deployment flow (how it actually deploys)

Both auto-deploy and manual deploy connect to the VM with SSH (`appleboy/ssh-action`) and run `scripts/deploy-vm.sh` in `VM_APP_DIR`.

`deploy-vm.sh` does:
1. Fetch/reset code to `origin/main`
2. Ensure `.env` exists
3. Pull/build containers
4. Start `db` and `redis`
5. Run migrations (`docker compose --profile setup run --rm migrate`)
6. Start app stack (`docker compose up -d --remove-orphans`)
7. Health check (`curl -fsS http://localhost/api/health`)

## Rollback options

- Quick rollback one commit:
  - Run workflow: `Rollback`
  - Effect: `git reset --hard HEAD^` on VM, then runs deploy script

- Rollback to an exact ref:
  - Run workflow: `Rollback To Ref`
  - Inputs:
    - `rollback_ref`: commit SHA, tag, or branch
    - `confirm`: must be exactly `ROLLBACK`
  - Effect: resolves ref, checks out detached commit, rebuilds/restarts stack, runs health check

## Required repo configuration

- Secrets:
  - `VM_HOST`
  - `VM_USER`
  - `SSH_PRIVATE_KEY`
- Variables:
  - `VM_APP_DIR`

Also required on VM:
- `.env` file in `VM_APP_DIR`
- Docker + Compose available
