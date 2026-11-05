#!/usr/bin/env bash
# Self-healing SSH local forwards for local development (run inside WSL/Linux):
#   127.0.0.1:11434 -> Qwen/Ollama on the GPU host (its own 127.0.0.1:11434)
#   127.0.0.1:2358  -> Judge0 on its private address
#
# Every CHECK_SECONDS it probes each forward with a real HTTP request; a forward that does
# not answer is torn down and re-created. Forwards bind to 127.0.0.1 only — nothing is
# exposed and nothing on the EC2 hosts is changed.
#
# Configuration (environment; no secrets are stored in this file):
#   QWEN_SSH_KEY, QWEN_SSH_HOST          e.g. ~/ec2/CareerSphere.pem, ubuntu@<qwen host>
#   JUDGE0_SSH_KEY, JUDGE0_SSH_HOST      e.g. ~/ec2/careersphere-judge0.pem, ubuntu@<judge0 host>
#   JUDGE0_PRIVATE_ADDR                  Judge0 address as seen from its host (e.g. 172.31.x.x)
#   CHECK_SECONDS (default 15), LOG_FILE (default ~/.cache/careersphere-tunnels.log)
# Either pair may be left unset to manage only the other tunnel.
#
# Stop it with:  pkill -f keep-tunnels.sh   (existing forwards keep running until they drop)
set -u

CHECK_SECONDS="${CHECK_SECONDS:-15}"
LOG_FILE="${LOG_FILE:-$HOME/.cache/careersphere-tunnels.log}"
mkdir -p "$(dirname "$LOG_FILE")"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"; }

SSH_OPTS=(-f -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3
          -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)

healthy() {  # any HTTP response (even 401) means the forward and the service answer
  local code
  code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$1" || true)
  [ -n "$code" ] && [ "$code" != "000" ]
}

ensure() {  # name local_port remote_target key host probe_url
  local name=$1 port=$2 target=$3 key=$4 host=$5 url=$6
  healthy "$url" && return 0
  log "$name: not answering on 127.0.0.1:$port — reconnecting"
  pkill -f -- "-L 127.0.0.1:$port:" 2>/dev/null || true
  pkill -f -- "-L $port:" 2>/dev/null || true
  sleep 1
  if ssh -i "$key" "${SSH_OPTS[@]}" -L "127.0.0.1:$port:$target" "$host" 2>>"$LOG_FILE"; then
    sleep 2
    if healthy "$url"; then log "$name: restored"; else log "$name: forward up but service not answering yet"; fi
  else
    log "$name: ssh failed (will retry in ${CHECK_SECONDS}s)"
  fi
}

log "keep-tunnels started (pid $$)"
while true; do
  if [ -n "${QWEN_SSH_KEY:-}" ] && [ -n "${QWEN_SSH_HOST:-}" ]; then
    ensure qwen 11434 127.0.0.1:11434 "$QWEN_SSH_KEY" "$QWEN_SSH_HOST" "http://127.0.0.1:11434/api/tags"
  fi
  if [ -n "${JUDGE0_SSH_KEY:-}" ] && [ -n "${JUDGE0_SSH_HOST:-}" ] && [ -n "${JUDGE0_PRIVATE_ADDR:-}" ]; then
    ensure judge0 2358 "$JUDGE0_PRIVATE_ADDR:2358" "$JUDGE0_SSH_KEY" "$JUDGE0_SSH_HOST" "http://127.0.0.1:2358/about"
  fi
  sleep "$CHECK_SECONDS"
done
