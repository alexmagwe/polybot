"""
Telegram notifier for Polymarket bot.
Sends alerts directly to Telegram without relying on Nanoclaw.
"""

import urllib.request
import urllib.parse
import json
import os
import logging

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_telegram(message: str) -> bool:
    """Send a message to Telegram. Returns True if successful."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not set — skipping notification")
        return False

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")
        return False


def notify_signal(signal: dict):
    """Send a signal alert to Telegram."""
    direction = signal.get("direction", "N/A")
    market = signal.get("market_name", "Unknown Market")[:80]
    price = signal.get("market_price", 0)
    fair = signal.get("fair_value", 0)
    edge = signal.get("edge", 0)
    size = signal.get("position_size", 0)
    strategy = signal.get("strategy", "N/A")
    confidence = signal.get("confidence", "N/A")

    msg = (
        f"🚨 <b>Signal Alert</b>\n\n"
        f"<b>{market}</b>\n\n"
        f"• Direction: <b>{direction}</b>\n"
        f"• Market Price: {price:.0%}\n"
        f"• Our Fair Value: {fair:.0%}\n"
        f"• Edge: <b>{edge:+.1%}</b>\n"
        f"• Confidence: {confidence}\n"
        f"• Strategy: {strategy}\n"
        f"• Suggested Position: <b>${size:.2f}</b>"
    )
    send_telegram(msg)


def notify_daily_pnl(portfolio: dict):
    """Send daily P&L report to Telegram."""
    cash = portfolio.get("cash", 100)
    initial = portfolio.get("initial_capital", 100)
    open_pos = len(portfolio.get("open_positions", []))
    closed_pos = len(portfolio.get("closed_positions", []))
    fees = portfolio.get("total_fees_paid", 0)
    pnl = cash - initial
    roi = (pnl / initial) * 100

    wins = sum(1 for p in portfolio.get("closed_positions", []) if p.get("pnl", 0) > 0)
    win_rate = (wins / closed_pos * 100) if closed_pos > 0 else 0

    emoji = "📈" if pnl >= 0 else "📉"

    msg = (
        f"📊 <b>Daily P&L Report</b>\n\n"
        f"• Portfolio Value: <b>${cash:.2f}</b>\n"
        f"• Total P&L: <b>{emoji} ${pnl:+.2f} ({roi:+.1f}%)</b>\n"
        f"• Open Positions: {open_pos}\n"
        f"• Closed Trades: {closed_pos}\n"
        f"• Win Rate: {win_rate:.0f}%\n"
        f"• Fees Paid: ${fees:.2f}"
    )
    send_telegram(msg)


def notify_startup():
    """Send startup notification."""
    send_telegram(
        "🤖 <b>Polymarket Bot Started</b>\n\n"
        "Scanning Politics/Macro markets every 30 minutes.\n"
        "You'll be notified when HIGH confidence signals are found."
    )


def notify_error(error: str):
    """Send error notification."""
    send_telegram(f"⚠️ <b>Bot Error</b>\n\n{error[:200]}")
