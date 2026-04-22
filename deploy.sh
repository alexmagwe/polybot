#!/bin/bash
# Polymarket Bot — Azure VM Deployment Script
# Run this on a fresh Ubuntu 24.04 VM as the default user (ubuntu/azureuser)
# Usage: bash deploy.sh YOUR_TELEGRAM_BOT_TOKEN YOUR_TELEGRAM_CHAT_ID

set -e

TELEGRAM_BOT_TOKEN="${1:-}"
TELEGRAM_CHAT_ID="${2:-}"
GITHUB_REPO="https://github.com/alexmagwe/polybot.git"
BOT_DIR="$HOME/polybot"
SERVICE_NAME="polymarket-bot"

echo "======================================"
echo "  Polymarket Bot — Azure Deployment"
echo "======================================"

# 1. Update system
echo "[1/6] Updating system packages..."
sudo apt-get update -q
sudo apt-get install -y -q python3 python3-pip python3-venv git curl

# 2. Clone or update repo
echo "[2/6] Cloning bot from GitHub..."
if [ -d "$BOT_DIR" ]; then
    cd "$BOT_DIR" && git pull
else
    git clone "$GITHUB_REPO" "$BOT_DIR"
fi
cd "$BOT_DIR"

# 3. Set up Python virtual environment
echo "[3/6] Setting up Python environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install flask apscheduler requests numpy -q

# 4. Create .env file
echo "[4/6] Creating config..."
cat > "$BOT_DIR/.env" << EOF
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
PAPER_TRADING=true
EOF
echo ".env created."

# 5. Create systemd service
echo "[5/6] Installing systemd service..."
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Polymarket Trading Signal Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${BOT_DIR}
EnvironmentFile=${BOT_DIR}/.env
ExecStart=${BOT_DIR}/venv/bin/python3 server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl restart ${SERVICE_NAME}

# 6. Verify
echo "[6/6] Verifying bot is running..."
sleep 3
if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
    echo ""
    echo "======================================"
    echo "  ✅ Bot is running successfully!"
    echo "======================================"
    echo ""
    echo "Useful commands:"
    echo "  Check status:  sudo systemctl status ${SERVICE_NAME}"
    echo "  View logs:     sudo journalctl -u ${SERVICE_NAME} -f"
    echo "  Restart bot:   sudo systemctl restart ${SERVICE_NAME}"
    echo "  Stop bot:      sudo systemctl stop ${SERVICE_NAME}"
    echo "  Check signals: curl http://localhost:5000/signals"
    echo "  Portfolio:     curl http://localhost:5000/portfolio"
else
    echo "❌ Bot failed to start. Check logs:"
    sudo journalctl -u ${SERVICE_NAME} -n 20 --no-pager
    exit 1
fi
