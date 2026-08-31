#!/usr/bin/env bash
#
# Per-boot startup for the Collectra HQ development environment: make sure the
# Docker daemon is up (configured for this nested VM) and that the backend
# service containers are running. Idempotent — safe to run repeatedly.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HQ_DIR="$REPO_ROOT/collectra-hq"
DOCKER_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/dockerhq"

log() { printf '\n=== %s ===\n' "$*"; }

log "Configuring Docker daemon for a nested VM (vfs storage driver)"
# overlay2 cannot mount inside this nested container; fall back to vfs and the
# classic (non-containerd) image store.
if [ ! -f /etc/docker/daemon.json ]; then
    printf '{\n  "storage-driver": "vfs",\n  "features": { "containerd-snapshotter": false }\n}\n' \
        | sudo tee /etc/docker/daemon.json >/dev/null
fi

log "Starting the Docker daemon"
if ! docker info >/dev/null 2>&1; then
    sudo service docker start || sudo dockerd >/tmp/dockerd.log 2>&1 &
    for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
fi
# Let the non-root user talk to the daemon in this session.
sudo chmod 666 /var/run/docker.sock || true

log "Allowing inter-container traffic (legacy iptables FORWARD policy)"
# Docker programs its rules in the nft backend, but a legacy-iptables FORWARD
# policy of DROP silently blocks container-to-container traffic in this VM.
sudo iptables-legacy -P FORWARD ACCEPT 2>/dev/null || true

log "Raising vm.max_map_count for Elasticsearch"
sudo sysctl -w vm.max_map_count=262144 >/dev/null 2>&1 || true

log "Preparing the Elasticsearch data volume"
# Elasticsearch runs as uid 1000 inside the container and needs to own its data
# directory on the host bind mount.
mkdir -p "$DOCKER_DATA_HOME/elasticsearch6"
sudo chown -R 1000:1000 "$DOCKER_DATA_HOME/elasticsearch6" || true

log "Starting backend service containers"
cd "$HQ_DIR"
export COMMCARE_HOST="http://localhost:8000"
bash scripts/docker up -d \
    postgres couch redis elasticsearch6 zookeeper kafka minio
bash scripts/docker up -d --force-recreate formplayer

log "Waiting for PostgreSQL and Kafka to become healthy"
until docker exec hqservice-postgres-1 pg_isready -U commcarehq -d commcarehq >/dev/null 2>&1; do
    sleep 2
done
for _ in $(seq 1 60); do
    status="$(docker inspect hqservice-kafka-1 --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null || true)"
    [ "$status" = "healthy" ] && break
    sleep 2
done

log "Backend services are up"
docker ps --format '{{.Names}}\t{{.Status}}'
