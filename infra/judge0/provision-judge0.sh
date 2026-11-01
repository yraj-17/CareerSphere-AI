#!/usr/bin/env bash
# Install Judge0 CE on a dedicated Linux VM (local Vagrant VM or a cloud CPU VM).
#
# Required: cgroup v1 (run provision-cgroup.sh and reboot first).
# Env:
#   JUDGE0_BIND_IP   private IP to publish the API on (never 0.0.0.0 on a public host)
#   JUDGE0_VERSION   default 1.13.1
set -euo pipefail

JUDGE0_VERSION="${JUDGE0_VERSION:-1.13.1}"
JUDGE0_BIND_IP="${JUDGE0_BIND_IP:?set JUDGE0_BIND_IP to the private IP the backend will call}"
INSTALL_DIR=/opt/judge0

if [ "$(stat -fc %T /sys/fs/cgroup)" = "cgroup2fs" ]; then
  echo "ERROR: this host is on cgroup v2. Run provision-cgroup.sh and reboot first." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl unzip
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
apt-get install -y unzip >/dev/null

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
if [ ! -f docker-compose.yml ]; then
  curl -fsSL -o judge0.zip "https://github.com/judge0/judge0/releases/download/v${JUDGE0_VERSION}/judge0-v${JUDGE0_VERSION}.zip"
  unzip -o -q judge0.zip
  cp -r "judge0-v${JUDGE0_VERSION}"/* .
  rm -rf judge0.zip "judge0-v${JUDGE0_VERSION}"
fi

# Publish the API on the private IP only. (Docker-published ports bypass ufw, so the
# bind address — not the firewall — is what keeps the API off public interfaces.)
sed -i -E "s#- \"([0-9.]+:)?2358:2358\"#- \"${JUDGE0_BIND_IP}:2358:2358\"#" docker-compose.yml

# Generate secrets once and keep them across re-provisioning.
CREDS="$INSTALL_DIR/credentials.env"
if [ ! -f "$CREDS" ]; then
  umask 077
  {
    echo "JUDGE0_URL=http://${JUDGE0_BIND_IP}:2358"
    echo "JUDGE0_AUTH_TOKEN=$(openssl rand -hex 32)"
    echo "JUDGE0_AUTHZ_TOKEN=$(openssl rand -hex 32)"
    echo "JUDGE0_REDIS_PASSWORD=$(openssl rand -hex 24)"
    echo "JUDGE0_POSTGRES_PASSWORD=$(openssl rand -hex 24)"
  } > "$CREDS"
fi
# shellcheck disable=SC1090
source "$CREDS"

setconf() {  # setconf KEY VALUE — replace or append in judge0.conf
  if grep -qE "^$1=" judge0.conf; then
    sed -i -E "s#^$1=.*#$1=$2#" judge0.conf
  else
    echo "$1=$2" >> judge0.conf
  fi
}
setconf REDIS_PASSWORD "$JUDGE0_REDIS_PASSWORD"
setconf POSTGRES_PASSWORD "$JUDGE0_POSTGRES_PASSWORD"
# Authentication: every request must carry X-Auth-Token. Admin endpoints need X-Auth-User.
setconf AUTHN_HEADER "X-Auth-Token"
setconf AUTHN_TOKEN "$JUDGE0_AUTH_TOKEN"
setconf AUTHZ_HEADER "X-Auth-User"
setconf AUTHZ_TOKEN "$JUDGE0_AUTHZ_TOKEN"
# Sandbox policy: no network, bounded CPU/wall/memory/processes/output.
setconf ENABLE_NETWORK "false"
setconf ALLOW_ENABLE_NETWORK "false"
setconf CPU_TIME_LIMIT "2"
setconf MAX_CPU_TIME_LIMIT "10"
setconf CPU_EXTRA_TIME "0.5"
setconf WALL_TIME_LIMIT "5"
setconf MAX_WALL_TIME_LIMIT "20"
setconf MEMORY_LIMIT "256000"
setconf MAX_MEMORY_LIMIT "512000"
setconf STACK_LIMIT "64000"
setconf MAX_PROCESSES_AND_OR_THREADS "64"
setconf MAX_FILE_SIZE "1024"
# The backend submits asynchronously and polls; no blocking waits, no callbacks.
setconf ENABLE_WAIT_RESULT "false"
setconf ENABLE_CALLBACKS "false"
setconf ENABLE_BATCHED_SUBMISSIONS "true"
setconf MAX_SUBMISSION_BATCH_SIZE "20"
setconf ENABLE_ADDITIONAL_FILES "false"
setconf MAX_QUEUE_SIZE "200"
chmod 600 judge0.conf

docker compose up -d db redis
sleep 10
docker compose up -d
echo "Waiting for Judge0 API..."
for _ in $(seq 1 60); do
  if curl -fsS -H "X-Auth-Token: ${JUDGE0_AUTH_TOKEN}" "http://${JUDGE0_BIND_IP}:2358/languages" >/dev/null 2>&1; then
    echo "Judge0 is up at http://${JUDGE0_BIND_IP}:2358"
    echo "Backend settings are in ${CREDS} (JUDGE0_URL and JUDGE0_AUTH_TOKEN)."
    exit 0
  fi
  sleep 5
done
echo "ERROR: Judge0 did not become ready; check 'docker compose logs' in ${INSTALL_DIR}" >&2
exit 1
