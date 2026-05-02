#!/usr/bin/env bash
set -euo pipefail

# Linen Draper Deployment Script
# Sets up a Reflex app behind Caddy + Anubis on Ubuntu.
#
# Architecture:
#   Internet -> Caddy (:443, TLS) -> Anubis (:8080) -> Reflex frontend (:3000)
#                                      Reflex backend (:8000) for API/WebSocket

APP_NAME="linen-draper"
APP_USER="linen-draper"
APP_DIR="/opt/${APP_NAME}"
ENV_FILE="/etc/${APP_NAME}/env"
DOMAIN="${1:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[x]${NC} $*"; exit 1; }

if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain>"
    echo "Example: $0 app.example.com"
    exit 1
fi

# ── Prerequisites ────────────────────────────────────────────────────────────

log "Checking prerequisites..."

if [ "$(id -u)" -ne 0 ]; then
    err "This script must be run as root (or with sudo)."
fi

UV_INSTALL_DIR="/usr/local/bin"

if [ ! -x "${UV_INSTALL_DIR}/uv" ]; then
    warn "Installing uv to ${UV_INSTALL_DIR}..."
    curl -LsSf https://astral.sh/uv/install.sh \
        | env UV_INSTALL_DIR="${UV_INSTALL_DIR}" sh
fi

# Verify uv is findable
UV="${UV_INSTALL_DIR}/uv"
if [ ! -x "$UV" ]; then
    # Fallback: check if it installed to root's home despite our env var
    if [ -x "/root/.local/bin/uv" ]; then
        UV="/root/.local/bin/uv"
    else
        err "uv not found at ${UV}. Install failed."
    fi
fi

command -v docker >/dev/null 2>&1 || {
    warn "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
}

if ! command -v caddy >/dev/null 2>&1; then
    warn "Installing Caddy..."
    apt-get update -qq
    apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy
fi

# ── System User ──────────────────────────────────────────────────────────────

log "Creating system user '${APP_USER}'..."
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    useradd --system --home-dir "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi

# ── Application Directory ────────────────────────────────────────────────────

log "Setting up application directory..."
mkdir -p "${APP_DIR}" /etc/"${APP_NAME}"

if [ -f pyproject.toml ]; then
    log "Copying project files to ${APP_DIR}..."
    rsync -a --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
        --exclude '*.pyc' --exclude '.web' --exclude '.states' \
        --exclude 'frontend.zip' --exclude 'backend.zip' \
        --exclude 'reflex.db' --exclude '.emails' --exclude '.pytest_cache' \
        ./ "${APP_DIR}/"
fi

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# ── Environment File ─────────────────────────────────────────────────────────

log "Configuring production settings..."
echo ""

read -p "  SMTP host (e.g. smtp.gmail.com): " SMTP_HOST
SMTP_HOST="${SMTP_HOST:-smtp.example.com}"

read -p "  SMTP port [587]: " SMTP_PORT
SMTP_PORT="${SMTP_PORT:-587}"

read -p "  SMTP username: " SMTP_USER
SMTP_USER="${SMTP_USER:-your-smtp-user}"

read -s -p "  SMTP password: " SMTP_PASSWORD
echo ""
SMTP_PASSWORD="${SMTP_PASSWORD:-your-smtp-password}"

read -p "  SMTP from address (e.g. noreply@${DOMAIN}): " SMTP_FROM
SMTP_FROM="${SMTP_FROM:-noreply@${DOMAIN}}"

read -p "  Anubis PoW difficulty [4]: " ANUBIS_DIFFICULTY
ANUBIS_DIFFICULTY="${ANUBIS_DIFFICULTY:-4}"

echo ""
log "Writing environment file to ${ENV_FILE}..."
cat > "${ENV_FILE}" <<EOF
# Linen Draper Production Environment
APP_ENV=production
LINEN_DRAPER_ENV=production

# SMTP Configuration
SMTP_HOST=${SMTP_HOST}
SMTP_PORT=${SMTP_PORT}
SMTP_USER=${SMTP_USER}
SMTP_PASSWORD=${SMTP_PASSWORD}
SMTP_FROM=${SMTP_FROM}

# Browser-accessible backend URL
API_URL=https://${DOMAIN}
EOF

chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

# ── Install Dependencies ─────────────────────────────────────────────────────

log "Installing Python dependencies (this may take a while)..."
cd "${APP_DIR}"
sudo -u "${APP_USER}" "${UV}" sync --frozen

# ── Database Migration ───────────────────────────────────────────────────────

log "Running database migrations..."
sudo -u "${APP_USER}" "${UV}" run reflex db migrate

# ── Frontend Artifacts ────────────────────────────────────────────────────────

# The production frontend build is memory-hungry and may OOM on small VPS.
# Build artifacts locally on your workstation and rsync them to the server:
#
#   On your local machine:
#     API_URL="https://${DOMAIN}" uv run reflex export
#     rsync -az frontend.zip backend.zip ${DOMAIN}:~/
#
#   Then re-run this script.

if [ -f "${APP_DIR}/frontend.zip" ] && [ -f "${APP_DIR}/backend.zip" ]; then
    log "Extracting pre-built artifacts..."
    sudo -u "${APP_USER}" unzip -o "${APP_DIR}/frontend.zip" -d "${APP_DIR}/" 2>/dev/null || \
        sudo -u "${APP_USER}" python3 -m zipfile -e "${APP_DIR}/frontend.zip" "${APP_DIR}/"
    sudo -u "${APP_USER}" unzip -o "${APP_DIR}/backend.zip" -d "${APP_DIR}/" 2>/dev/null || \
        sudo -u "${APP_USER}" python3 -m zipfile -e "${APP_DIR}/backend.zip" "${APP_DIR}/"
fi


# ── Systemd Service ──────────────────────────────────────────────────────────

log "Installing systemd service..."
cp "${APP_DIR}/deploy/linen-draper.service" /etc/systemd/system/
sed -i "s|/opt/linen-draper|${APP_DIR}|g" /etc/systemd/system/linen-draper.service
sed -i "s|/etc/linen-draper/env|${ENV_FILE}|g" /etc/systemd/system/linen-draper.service
systemctl daemon-reload
systemctl enable linen-draper.service

# ── Anubis Container ─────────────────────────────────────────────────────────

log "Pulling Anubis proof-of-work filter container..."
docker pull ghcr.io/xe/anubis:latest 2>/dev/null || \
    warn "Could not pull Anubis image. Skipping container setup."

# ── Caddy Configuration ──────────────────────────────────────────────────────

log "Configuring Caddy..."
CADDYFILE="/etc/caddy/Caddyfile.${APP_NAME}"
cp "${APP_DIR}/deploy/Caddyfile" "${CADDYFILE}"
sed -i "s/linen-draper.example.com/${DOMAIN}/g" "${CADDYFILE}"

if ! grep -q "import ${CADDYFILE}" /etc/caddy/Caddyfile 2>/dev/null; then
    echo "import ${CADDYFILE}" >> /etc/caddy/Caddyfile
fi

# ── Start Everything ─────────────────────────────────────────────────────────

log "Starting services..."
systemctl reload caddy
systemctl start linen-draper.service

docker rm -f anubis 2>/dev/null || true
docker run -d \
    --name anubis \
    --restart unless-stopped \
    --net=host \
    -e ANUBIS_TARGET="http://localhost:3000" \
    -e ANUBIS_BIND=":8080" \
    -e ANUBIS_DIFFICULTY="${ANUBIS_DIFFICULTY}" \
    ghcr.io/xe/anubis:latest

log ""
log "============================================================"
log "Deployment complete!"
log ""
log "Next steps:"
log "  1. Register an account: https://${DOMAIN}/register"
log "  2. Check status:  systemctl status linen-draper"
log "  3. View logs:     journalctl -u linen-draper -f"
log "  4. Caddy logs:    journalctl -u caddy -f"
log "  5. Anubis logs:   docker logs -f anubis"
log "============================================================"
