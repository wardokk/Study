"""
Discord notifier: sends alerts and reports via webhook.
Supports rate-limit-safe batching and embed formatting.
"""

import logging
import time
from datetime import datetime
from typing import Optional

import requests

from config import DISCORD_WEBHOOK_URL, DISCORD_ALERT_WEBHOOK_URL

logger = logging.getLogger(__name__)

_last_send_time = 0.0
_RATE_LIMIT_SECONDS = 1.0   # Discord allows ~50 req/s per webhook; we stay conservative


def _post_webhook(payload: dict, webhook_url: str = DISCORD_WEBHOOK_URL) -> bool:
    global _last_send_time
    if not webhook_url:
        logger.warning("Discord webhook URL not configured — skipping notification")
        return False

    # Gentle rate limiting
    elapsed = time.time() - _last_send_time
    if elapsed < _RATE_LIMIT_SECONDS:
        time.sleep(_RATE_LIMIT_SECONDS - elapsed)

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        _last_send_time = time.time()

        if resp.status_code == 429:   # Rate limited
            retry_after = resp.json().get("retry_after", 2.0)
            logger.warning("Discord rate limited. Waiting %.1fs", retry_after)
            time.sleep(retry_after)
            resp = requests.post(webhook_url, json=payload, timeout=10)

        if resp.status_code in (200, 204):
            return True

        logger.error("Discord webhook failed: %s %s", resp.status_code, resp.text[:200])
        return False

    except Exception as exc:
        logger.error("Discord send error: %s", exc)
        return False


def send_signal_alert(signal_embed: dict) -> bool:
    """Send a FinalSignal embed to the alert webhook."""
    return _post_webhook(signal_embed, DISCORD_ALERT_WEBHOOK_URL)


def send_price_alert(message: str) -> bool:
    """Send a plain price movement alert."""
    payload = {
        "embeds": [{
            "title": "💰 Price Alert",
            "description": message,
            "color": 0xFFAA00,
            "footer": {"text": f"Stock Bot • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
        }]
    }
    return _post_webhook(payload, DISCORD_ALERT_WEBHOOK_URL)


def send_news_alert(title: str, summary: str, url: str, source: str,
                    sentiment: float, tickers: list[str]) -> bool:
    """Send a high-impact news alert."""
    color = 0x00CC66 if sentiment > 0.15 else (0xFF4444 if sentiment < -0.15 else 0x888888)
    sentiment_label = ("🟢 Bullish" if sentiment > 0.15 else
                       "🔴 Bearish" if sentiment < -0.15 else "⚪ Neutral")
    ticker_str = " ".join(f"`{t}`" for t in tickers) if tickers else "General Market"

    payload = {
        "embeds": [{
            "title": f"📰 {title[:200]}",
            "description": summary[:400] + ("..." if len(summary) > 400 else ""),
            "url": url,
            "color": color,
            "fields": [
                {"name": "Source", "value": source, "inline": True},
                {"name": "Sentiment", "value": sentiment_label, "inline": True},
                {"name": "Tickers", "value": ticker_str, "inline": True},
            ],
            "footer": {"text": f"Stock Bot News • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
        }]
    }
    return _post_webhook(payload)


def send_twitter_alert(author: str, text: str, tier: str, tickers: list[str],
                       is_insider_risk: bool = False, alert_level: str = "MEDIUM") -> bool:
    """Send a notable tweet alert."""
    tier_badge = {"REGULATORY": "🏛️ REGULATORY", "INSTITUTIONAL": "🏦 INSTITUTIONAL",
                  "OPINION": "💬 OPINION"}.get(tier, tier)
    color = {"HIGH": 0xFF2222, "MEDIUM": 0xFFAA00, "LOW": 0x888888}.get(alert_level, 0x888888)

    risk_note = "\n\n⚠️ **INSIDER RISK FLAG** — This post contains specific forward-looking language from a non-regulatory source. Treat with caution." if is_insider_risk else ""

    ticker_str = " ".join(f"`{t}`" for t in tickers) if tickers else "General Market"
    payload = {
        "embeds": [{
            "title": f"🐦 @{author} [{tier_badge}]",
            "description": text[:500] + risk_note,
            "color": color,
            "fields": [
                {"name": "Tickers Mentioned", "value": ticker_str, "inline": True},
                {"name": "Alert Level", "value": alert_level, "inline": True},
            ],
            "footer": {"text": f"Stock Bot X/Twitter Monitor • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
        }]
    }
    return _post_webhook(payload, DISCORD_ALERT_WEBHOOK_URL)


def send_hourly_summary(signals: list, market_sentiment: float) -> bool:
    """Send a full hourly summary of all watchlist signals."""
    if not signals:
        return False

    long_signals = [s for s in signals if s.final_action == "LONG"]
    short_signals = [s for s in signals if s.final_action == "SHORT"]
    hold_signals = [s for s in signals if s.final_action == "HOLD"]

    def fmt_list(items) -> str:
        if not items:
            return "None"
        return ", ".join(f"**{s.ticker}** ({s.confidence})" for s in items[:10])

    overall_bias = "🟢 BULLISH" if market_sentiment > 0.15 else ("🔴 BEARISH" if market_sentiment < -0.15 else "⚪ NEUTRAL")

    payload = {
        "embeds": [{
            "title": "📊 Hourly Market Summary",
            "color": 0x5865F2,
            "fields": [
                {"name": "Overall Market Bias", "value": overall_bias, "inline": False},
                {"name": f"📈 LONG ({len(long_signals)})", "value": fmt_list(long_signals), "inline": False},
                {"name": f"📉 SHORT ({len(short_signals)})", "value": fmt_list(short_signals), "inline": False},
                {"name": f"⏸️ HOLD ({len(hold_signals)})", "value": fmt_list(hold_signals), "inline": False},
            ],
            "footer": {"text": f"Stock Bot Summary • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
        }]
    }
    return _post_webhook(payload)


def send_startup_message(watchlist: list[str]) -> bool:
    """Announce bot startup."""
    payload = {
        "embeds": [{
            "title": "🤖 Stock Analysis Bot — Online",
            "description": (
                "I am now monitoring the market and will send you:\n"
                "• 📈 Technical signals (RSI, MACD, Moving Averages, Bollinger Bands)\n"
                "• 📰 High-impact news from Reuters, Bloomberg, CNBC, WSJ, FT\n"
                "• 🐦 X/Twitter alerts from verified institutional accounts\n"
                "• 💰 Price movement alerts (≥2% moves)\n"
                "• 📊 Hourly summary with LONG / SHORT / HOLD recommendations"
            ),
            "color": 0x5865F2,
            "fields": [
                {"name": "Watchlist", "value": " ".join(f"`{t}`" for t in watchlist), "inline": False},
                {"name": "Data Sources", "value": "yfinance, NewsAPI, Finnhub, RSS Feeds, X/Twitter API", "inline": False},
            ],
            "footer": {"text": f"Started at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
        }]
    }
    return _post_webhook(payload)
