#!/usr/bin/env bash
# deploy.sh — first-time setup on a fresh Hetzner CX22 (Ubuntu 24.04)
# Usage: bash deploy.sh YOUR_DOMAIN
# e.g.:  bash deploy.sh clonehero.example.com
set -euo pipefail

DOMAIN="${1:?Usage: bash deploy.sh YOUR_DOMAIN}"
APP_DIR="/opt/clone-hero-downloader"

# ── 1. System packages ────────────────────────────────────────────────────────
apt-get update -qq
apt-get install -y -qq docker.io docker-compose-plugin certbot ufw git

# ── 2. Firewall ───────────────────────────────────────────────────────────────
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ── 3. Clone / copy repo ──────────────────────────────────────────────────────
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  # Replace with your actual repo URL once you push to GitHub/GitLab
  git clone https://github.com/YOUR_USER/clone-hero-playlist-downloader.git "$APP_DIR"
fi

cd "$APP_DIR"

# ── 4. Create .env from example if missing ───────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — review it at $APP_DIR/.env"
fi

# ── 5. Replace YOUR_DOMAIN placeholder in nginx.conf ─────────────────────────
sed -i "s/YOUR_DOMAIN/$DOMAIN/g" nginx.conf

# ── 6. Obtain TLS cert (standalone, port 80 must be free) ────────────────────
certbot certonly --standalone --non-interactive --agree-tos \
  --register-unsafely-without-email \
  -d "$DOMAIN"

# ── 7. Build & start containers ──────────────────────────────────────────────
docker compose build --no-cache
docker compose up -d

echo ""
echo "Done! App running at https://$DOMAIN"
echo "To update later: cd $APP_DIR && git pull && docker compose up -d --build"
