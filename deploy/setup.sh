#!/usr/bin/env bash
set -euo pipefail

# MediBridge production deploy — Ubuntu 22.04/24.04 LTS
# (Oracle Cloud Always-Free Ampere A1 works great for this)
#
# Usage on your server:
#   cd medibridge
#   bash deploy/setup.sh

cd "$(dirname "$0")/.."

echo "==> Updating package lists"
sudo apt-get update -qq

echo "==> Installing Docker + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get install -y -qq ca-certificates curl
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
  else
    sudo apt-get install -y -qq docker.io docker-compose-v2 || sudo apt-get install -y -qq docker.io
  fi
fi

sudo usermod -aG docker "$USER" || true
sudo systemctl enable --now docker >/dev/null 2>&1 || true

echo "==> Building and starting containers (first build can take several minutes)"
sudo docker compose up -d --build

echo "==> Waiting for backend to report healthy"
for i in $(seq 1 24); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "    backend healthy after ~$((i * 5))s"
    break
  fi
  sleep 5
done

echo ""
echo "==> Deployment finished"
echo "    Open  http://YOUR_SERVER_PUBLIC_IP/  in a browser"
echo "    API   http://YOUR_SERVER_PUBLIC_IP/health"
echo "    Logs  sudo docker compose logs -f"
echo "    DB    stored in the 'backend-data' volume (survives restarts)"