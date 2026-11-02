#!/usr/bin/env bash
set -e

IMAGE="deep-research-api:hermes-test"
WORKDIR="/opt/data/projects/worktrees/wt-hermes-packaging"

docker build -f "$WORKDIR/Dockerfile.backend" -t "$IMAGE" "$WORKDIR"

docker run --rm "$IMAGE" bash -c "hermes --version | grep -q '0.19.0' && echo OK_VERSION && hermes profile list | grep -q deep-research && echo OK_PROFILE && python -c 'import app.main' && echo OK_IMPORT"
