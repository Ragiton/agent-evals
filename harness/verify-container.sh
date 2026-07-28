# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ragiton
#!/usr/bin/env bash
# Build and smoke-test the reproducible Agent Evals container.
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
IMAGE="${1:-${IMAGE:-agent-evals:9.0.8}}"

if ! command -v docker >/dev/null 2>&1; then
    printf 'error: docker is required to build and verify %s\n' "$IMAGE" >&2
    exit 127
fi

printf 'building image %s from %s\n' "$IMAGE" "$SCRIPT_DIR"
docker build --pull --tag "$IMAGE" "$SCRIPT_DIR"

printf 'running toolchain verification in %s\n' "$IMAGE"
docker run --rm "$IMAGE" verify

IMAGE_ID=$(docker image inspect --format '{{.Id}}' "$IMAGE")
printf 'image=%s\nimage_id=%s\n' "$IMAGE" "$IMAGE_ID"
