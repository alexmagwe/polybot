#!/usr/bin/env bash

BOT_DIR="/workspace/group/polymarket-bot"
cd "$BOT_DIR"

if [ ! -f bot.pid ]; then
    echo "No bot.pid file found. Server may not be running."
    exit 0
fi

PID=$(cat bot.pid)

if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping server (PID $PID)..."
    kill "$PID"
    sleep 2
    # Force kill if still alive
    if kill -0 "$PID" 2>/dev/null; then
        echo "Force killing..."
        kill -9 "$PID" 2>/dev/null || true
    fi
    echo "Server stopped."
else
    echo "Server (PID $PID) is not running."
fi

rm -f bot.pid
