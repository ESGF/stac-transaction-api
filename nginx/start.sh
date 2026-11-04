#!/usr/bin/env bash
set -Eeuo pipefail

nginx -t

nginx_pid=""
uvicorn_pid=""

shutdown() {
    trap - TERM INT

    # Gracefully drain nginx while Uvicorn is still available.
    if [[ -n "$nginx_pid" ]]; then
        kill -QUIT "$nginx_pid" 2>/dev/null || true
        wait "$nginx_pid" 2>/dev/null || true
    fi

    if [[ -n "$uvicorn_pid" ]]; then
        kill -TERM "$uvicorn_pid" 2>/dev/null || true
        wait "$uvicorn_pid" 2>/dev/null || true
    fi
}

trap 'shutdown; exit 0' TERM INT

"$@" &
uvicorn_pid=$!

nginx -g 'daemon off;' &
nginx_pid=$!

# If either process exits, stop the other and fail the container.
# ECS can then replace the task.
set +e
wait -n "$uvicorn_pid" "$nginx_pid"
status=$?
set -e

shutdown

if [[ "$status" -eq 0 ]]; then
    status=1
fi

exit "$status"