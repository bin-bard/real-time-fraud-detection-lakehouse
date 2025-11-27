#!/usr/bin/env bash
# Cleanup containers, networks, volumes (use with caution)
set -euo pipefail

echo "Stopping and removing containers..."
docker compose down -v --remove-orphans || docker-compose down -v --remove-orphans || true

echo "Pruning unused resources (confirm prompts may appear)"
docker system prune -f || true

echo "Done."
