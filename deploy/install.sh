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

command -v uv >/dev/null 2>&1 || {
    warn "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    source $HOME/.local/bin/env
}

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

# Copy the current directory contents to the app dir (if running from the repo)
# In production, you'd clone the repo. For a fresh clone:
# git clone https://github.com/sam/linen-draper.git "${APP_DIR}"

if [ -f pyproject.toml ]; then
    log "Copying project files from current directory to ${APP_DIR}..."
    rsync -a --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
        --exclude '*.pyc' --exclude '.web' --exclude '.states' \
        --exclude 'frontend.zip' --exclude 'backend.zip' \
        --exclude 'reflex.db' --exclude '.emails' \
        ./ "${APP_DIR}/"
fi

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# ── Environment File ─────────────────────────────────────────────────────────

log "Creating environment file..."
if [ ! -f "${ENV_FILE}" ]; then
    cat > "${ENV_FILE}" <<'EOF'
# Linen Draper Production Environment
APP_ENV=production
LINEN_DRAPER_ENV=production

# SMTP Configuration (required for production email sending)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=noreply@example.com

# Browser-accessible backend URL (must match Caddy domain)
API_URL=https://DOMAIN_PLACEHOLDER
EOF
    sed -i "s/DOMAIN_PLACEHOLDER/${DOMAIN}/g" "${ENV_FILE}"
    warn "Please edit ${ENV_FILE} with your SMTP credentials before starting."
fi

chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

# ── Install Dependencies ─────────────────────────────────────────────────────

log "Installing Python dependencies..."
cd "${APP_DIR}"
sudo -u "${APP_USER}" uv sync --frozen

# ── Database Migration ───────────────────────────────────────────────────────

log "Running database migrations..."
sudo -u "${APP_USER}" uv run reflex db migrate

# ── Build Frontend ───────────────────────────────────────────────────────────

log "Building production frontend..."
API_URL="https://${DOMAIN}" sudo -u "${APP_USER}" uv run reflex export --frontend-only

# ── Systemd Service ──────────────────────────────────────────────────────────

log "Installing systemd service..."
cp deploy/linen-draper.service /etc/systemd/system/
sed -i "s|/opt/linen-draper|${APP_DIR}|g" /etc/systemd/system/linen-draper.service
sed -i "s|/etc/linen-draper/env|${ENV_FILE}|g" /etc/systemd/system/linen-draper.service
systemctl daemon-reload
systemctl enable linen-draper.service

# ── Anubis Container ─────────────────────────────────────────────────────────

log "Setting up Anubis proof-of-work filter..."
docker pull ghcr.io/xe/anubis:latest 2>/dev/null || \
    docker pull ghcr.io/xe/anubis:latest || \
    warn "Could not pull Anubis image. Skipping container setup."

# ── Caddy Configuration ──────────────────────────────────────────────────────

log "Configuring Caddy..."
CADDYFILE="/etc/caddy/Caddyfile.${APP_NAME}"
cp deploy/Caddyfile "${CADDYFILE}"
sed -i "s/linen-draper.example.com/${DOMAIN}/g" "${CADDYFILE}"

if ! grep -q "import ${CADDYFILE}" /etc/caddy/Caddyfile 2>/dev/null; then
    echo "import ${CADDYFILE}" >> /etc/caddy/Caddyfile
fi

# ── Start Everything ─────────────────────────────────────────────────────────

log "Starting services..."
systemctl restart caddy
systemctl start linen-draper.service

# Start Anubis container
docker rm -f anubis 2>/dev/null || true
docker run -d \
    --name anubis \
    --restart unless-stopped \
    --net=host \
    -e ANUBIS_TARGET="http://localhost:3000" \
    -e ANUBIS_BIND=":8080" \
    -e ANUBIS_DIFFICULTY=4 \
    ghcr.io/xe/anubis:latest

log ""
log "============================================================"
log "Deployment complete!"
log ""
log "Next steps:"
log "  1. Edit ${ENV_FILE} with your SMTP credentials"
log "  2. Register an account: https://${DOMAIN}/register"
log "  3. Check status:  systemctl status linen-draper"
log "  4. View logs:     journalctl -u linen-draper -f"
log "  5. Caddy logs:    journalctl -u caddy -f"
log "  6. Anubis logs:   docker logs -f anubis"
log "============================================================"
