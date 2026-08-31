#!/usr/bin/env bash
# Bring up the Docker daemon and the collectra-hq backing services. Re-runnable.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HQ_DIR="$REPO_ROOT/collectra-hq"
DOCKER_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/dockerhq"

step() { printf '\n[services] %s\n' "$*"; }

# overlay2 can't mount in this nested VM, so run Docker on the vfs driver.
if [ ! -f /etc/docker/daemon.json ]; then
    printf '{\n  "storage-driver": "vfs",\n  "features": { "containerd-snapshotter": false }\n}\n' \
        | sudo tee /etc/docker/daemon.json >/dev/null
fi

step "Starting Docker daemon"
if ! docker info >/dev/null 2>&1; then
    sudo service docker start || sudo dockerd >/tmp/dockerd.log 2>&1 &
    for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
fi
sudo chmod 666 /var/run/docker.sock || true

# Docker manages its rules through nft, but a leftover legacy-iptables FORWARD
# policy of DROP blocks container-to-container traffic (e.g. Kafka -> Zookeeper).
sudo iptables-legacy -P FORWARD ACCEPT 2>/dev/null || true

# Elasticsearch 6 needs a higher mmap limit and ownership of its data volume.
sudo sysctl -w vm.max_map_count=262144 >/dev/null 2>&1 || true
mkdir -p "$DOCKER_DATA_HOME/elasticsearch6"
sudo chown -R 1000:1000 "$DOCKER_DATA_HOME/elasticsearch6" || true

step "Starting service containers"
cd "$HQ_DIR"
export COMMCARE_HOST="http://localhost:8000"
bash scripts/docker up -d postgres couch redis elasticsearch6 zookeeper kafka minio
bash scripts/docker up -d --force-recreate formplayer

step "Waiting for PostgreSQL and Kafka"
until docker exec hqservice-postgres-1 pg_isready -U commcarehq -d commcarehq >/dev/null 2>&1; do
    sleep 2
done
for _ in $(seq 1 60); do
    status="$(docker inspect hqservice-kafka-1 --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' 2>/dev/null || true)"
    [ "$status" = "healthy" ] && break
    sleep 2
done

docker ps --format '{{.Names}}\t{{.Status}}'
