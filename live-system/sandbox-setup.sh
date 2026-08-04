#!/usr/bin/env bash
# sandbox-setup.sh — Spin up, initialize, and tear down the osEngineer test sandbox.
#
# Usage:
#   ./sandbox-setup.sh start [--clean]
#   ./sandbox-setup.sh stop

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/sandbox-compose.yml"
SECRETS_FILE="$SCRIPT_DIR/../.osengineer/secrets.env"

log() { printf '[osEngineer Sandbox] %s\n' "$*"; }
warn() { printf '[osEngineer Sandbox] WARNING: %s\n' "$*" >&2; }
fail() { printf '[osEngineer Sandbox] ERROR: %s\n' "$*" >&2; exit 1; }

# Source local credentials if present
if [ -f "$SECRETS_FILE" ]; then
  # shellcheck disable=SC1090
  source "$SECRETS_FILE"
  log "Loaded secure secrets from .osengineer/secrets.env"
fi

# Resilient query_url function using curl or Python 3 HTTP fallback
query_url() {
  local method="$1"
  local url="$2"
  local token="${3:-}"
  local json_data="${4:-}"

  if command -v curl >/dev/null 2>&1; then
    local curl_opts=("-s" "-X" "$method")
    [ -n "$token" ] && curl_opts+=("-H" "X-Vault-Token: $token")
    if [ -n "$json_data" ]; then
      curl_opts+=("-H" "Content-Type: application/json" "-d" "$json_data")
    fi
    curl "${curl_opts[@]}" "$url"
  else
    # Python 3 HTTP fallback (standard library, no external deps)
    python3 - "$method" "$url" "$token" "$json_data" <<'PY'
import json, sys, urllib.request, urllib.error
method, url, token, json_data = sys.argv[1:5]
req = urllib.request.Request(url, method=method, data=json_data.encode() if json_data else None)
if token:
    req.add_header("X-Vault-Token", token)
if json_data:
    req.add_header("Content-Type", "application/json")
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        sys.stdout.write(resp.read().decode())
        sys.exit(0 if 200 <= resp.status < 300 else resp.status)
except urllib.error.HTTPError as e:
    sys.exit(e.code)
except Exception:
    sys.exit(1)
PY
  fi
}

start_sandbox() {
  local clean="${1:-}"
  
  if [ "$clean" = "--clean" ]; then
    log "Performing clean build of local sandbox..."
    docker-compose -f "$COMPOSE_FILE" down -v --remove-orphans || true
  fi

  log "Booting sandbox mock services..."
  docker-compose -f "$COMPOSE_FILE" up -d

  # 1. Wait for RabbitMQ Health Check
  log "Waiting for RabbitMQ to start..."
  local retries=12
  while [ $retries -gt 0 ]; do
    if docker exec SS-sandbox-rabbitmq rabbitmq-diagnostics check_running >/dev/null 2>&1; then
      log "  + RabbitMQ is ready!"
      break
    fi
    retries=$((retries - 1))
    sleep 5
  done
  [ $retries -eq 0 ] && fail "RabbitMQ failed to start in time."

  # 2. Wait for Vault Health Check
  log "Waiting for HashiCorp Vault to start..."
  retries=10
  while [ $retries -gt 0 ]; do
    if query_url GET "http://127.0.0.1:8200/v1/sys/health" >/dev/null 2>&1; then
      log "  + Vault is ready!"
      break
    fi
    retries=$((retries - 1))
    sleep 3
  done
  [ $retries -eq 0 ] && fail "Vault failed to start in time."

  # 3. Pre-warm Vault secrets via HTTP API using standard token
  log "Seeding mock credentials into local Vault..."
  local vault_token="${VAULT_TOKEN:-root-dev-token}"
  
  # Enable kv-v2 engine if not already enabled
  query_url POST "http://127.0.0.1:8200/v1/sys/mounts/secret" "$vault_token" '{"type":"kv-v2"}' >/dev/null || true

  # Write mock mission secrets
  query_url POST "http://127.0.0.1:8200/v1/secret/data/clearance/keys" "$vault_token" '{"data":{"mission_id":"MS-088","clearance_level":"secret","vault_key":"mock-auth-secret-12345"}}' >/dev/null

  log "Local Vault successfully seeded with mock credentials."
  log "Sandbox is fully operational."
}

stop_sandbox() {
  log "Shutting down sandbox Compose stack..."
  docker-compose -f "$COMPOSE_FILE" down -v --remove-orphans
  log "Sandbox successfully dismantled."
}

# ── Dispatch ───────────────────────────────────────────────────────────────

if [ $# -eq 0 ]; then
  cat <<USAGE
Usage:
  $0 start [--clean]
  $0 stop
USAGE
  exit 1
fi

case "$1" in
  start)
    start_sandbox "${2:-}"
    ;;
  stop)
    stop_sandbox
    ;;
  *)
    fail "Unknown command '$1'. Supported: start, stop"
    ;;
esac
