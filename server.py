#!/usr/bin/env python3
"""Persistent Flask server for the Polymarket paper trading bot.

Runs APScheduler to execute paper trading scans every 30 minutes.
Exposes REST endpoints for status, signals, portfolio, and reports.
"""

import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load .env file (for Azure/VPS deployment)
load_dotenv()

from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

# Ensure the bot directory is on the path — auto-detect from server.py location
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BOT_DIR)
os.chdir(BOT_DIR)

app = Flask(__name__)

# Logging
logging.basicConfig(
    filename=os.path.join(BOT_DIR, "bot.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("polymarket-bot")
# Also log to stdout so nohup captures it
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
logger.addHandler(console)

# Track last run info
last_run = {"timestamp": None, "summary": None, "error": None}
run_lock = threading.Lock()


def run_scan():
    """Execute a paper trading scan and save results."""
    global last_run
    logger.info("Starting scheduled paper trading scan...")
    try:
        from paper_trader import run_paper_trading
        from live_report import generate_live_report
        from notifier import notify_signal

        summary = run_paper_trading()

        # Save signals
        signals_path = os.path.join(BOT_DIR, "initial_signals.json")
        with open(signals_path, "w") as f:
            json.dump(summary, f, indent=2)

        # Generate report
        generate_live_report()

        with run_lock:
            last_run["timestamp"] = datetime.now(timezone.utc).isoformat()
            last_run["summary"] = summary
            last_run["error"] = None

        signals_found = summary.get("signals_found", 0)
        logger.info(
            "Scan complete: %d signals, %d trades",
            signals_found,
            summary.get("trades_executed", 0),
        )

        # Send Telegram alerts for HIGH confidence signals
        for signal in summary.get("signals", []):
            if signal.get("confidence") == "HIGH" and signal.get("edge", 0) >= 0.03:
                notify_signal(signal)

    except Exception as e:
        logger.exception("Scan failed: %s", e)
        with run_lock:
            last_run["timestamp"] = datetime.now(timezone.utc).isoformat()
            last_run["error"] = str(e)


@app.route("/")
def health():
    """Health check — returns bot status."""
    with run_lock:
        info = dict(last_run)
    return jsonify({
        "status": "running",
        "server_time": datetime.now(timezone.utc).isoformat(),
        "last_scan": info["timestamp"],
        "last_error": info["error"],
        "signals_found": (info["summary"] or {}).get("signals_found"),
        "trades_executed": (info["summary"] or {}).get("trades_executed"),
    })


@app.route("/signals")
def signals():
    """Return current signals from initial_signals.json."""
    path = os.path.join(BOT_DIR, "initial_signals.json")
    if os.path.exists(path):
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({"error": "No signals file found. Run a scan first."}), 404


@app.route("/portfolio")
def portfolio():
    """Return current paper portfolio from paper_trades.json."""
    path = os.path.join(BOT_DIR, "paper_trades.json")
    if os.path.exists(path):
        with open(path) as f:
            return jsonify(json.load(f))
    return jsonify({"error": "No portfolio file found."}), 404


@app.route("/report")
def report():
    """Return latest backtest_report.md as JSON."""
    path = os.path.join(BOT_DIR, "backtest_report.md")
    if os.path.exists(path):
        with open(path) as f:
            content = f.read()
        return jsonify({"report": content})
    return jsonify({"error": "No report file found."}), 404


@app.route("/run", methods=["POST"])
def manual_run():
    """Manually trigger a scan immediately."""
    logger.info("Manual scan triggered via /run endpoint")
    thread = threading.Thread(target=run_scan, daemon=True)
    thread.start()
    return jsonify({"status": "scan_started", "message": "Scan triggered in background."})


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Polymarket Bot Server starting up")
    logger.info("=" * 50)

    # Send startup notification
    try:
        from notifier import notify_startup
        notify_startup()
    except Exception:
        pass

    # Run first scan on startup
    logger.info("Running initial scan on startup...")
    run_scan()

    # Set up scheduler — every 30 minutes
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_scan, "interval", minutes=30, id="paper_trade_scan")
    scheduler.start()
    logger.info("Scheduler started: scans every 30 minutes")

    # Start Flask
    logger.info("Starting Flask server on port 5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
