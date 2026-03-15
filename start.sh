#!/usr/bin/env bash
set -e

BOT_DIR="/workspace/group/polymarket-bot"
cd "$BOT_DIR"

echo "=== Polymarket Bot - Starting ==="

# Install requirements
echo "[1/3] Installing requirements..."
pip3 install -q -r requirements.txt

# Stop existing server if running
if [ -f bot.pid ]; then
    OLD_PID=$(cat bot.pid)
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Stopping existing server (PID $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
    fi
    rm -f bot.pid
fi

# Start server
echo "[2/3] Starting server..."
nohup python3 server.py > bot.log 2>&1 &
echo $! > bot.pid
PID=$(cat bot.pid)

echo "[3/3] Server started with PID $PID"
sleep 3

# Verify
if kill -0 "$PID" 2>/dev/null; then
    echo "=== Server is running (PID $PID) ==="
    echo "Endpoints:"
    echo "  GET  http://localhost:5000/          - Health check"
    echo "  GET  http://localhost:5000/signals    - Current signals"
    echo "  GET  http://localhost:5000/portfolio  - Paper portfolio"
    echo "  GET  http://localhost:5000/report     - Backtest report"
    echo "  POST http://localhost:5000/run        - Trigger scan"
else
    echo "ERROR: Server failed to start. Check bot.log:"
    tail -20 bot.log
    exit 1
fi
