#!/usr/bin/env bash
# Build once (needs network), then run with none: `--network none` leaves the demo servers and sandbox
# unable to reach anything outside the container. Usage: docker/run.sh [command...]
set -e
cd "$(dirname "$0")/.."
docker build -t code-mode-demo .
if [ $# -eq 0 ]; then set -- python3 examples/minimal_code_mode.py; fi
docker run --rm --network none --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges \
  --memory 1g --pids-limit 128 code-mode-demo "$@"
