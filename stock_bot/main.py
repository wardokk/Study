"""
Stock Market Analysis Bot — Main Orchestrator
Runs continuously, scanning technical indicators, news, and X/Twitter.
Sends all alerts to Discord.

Usage:
    python main.py

Required environment variables (set in .env):
    DISCORD_WEBHOOK_URL         — main Discord webhook
    DISCORD_ALERT_WEBHOOK_URL   — (optional) separate channel for high-priority alerts
    NEWS_API_KEY                — newsapi.org key
    FINNHUB_API_KEY             — finnhub.io key
    TWITTER_BEARER_TOKEN        — X/Twitter API v2 bearer token
    ALPHA_VANTAGE_API_KEY       — (optional) for supplemental data
"""

import logging
import time
from datetime import datetime

from config import (
    WATCHLIST,
    MARKET_SCAN_INTERVAL,
    NEWS_SCAN_INTERVAL,
    TWITTER_SCAN_INTERVAL,
    SUMMARY_INTERVAL,
    PRICE_MOVE_ALERT_PCT,
    VOLUME_SPIKE_MULTIPLIER,
)
from market_analyzer import analyze_ticker, check_price_alert
from news_monitor import (
    fetch_rss_news,
    fetch_newsapi,
    fetch_finnhub_news,
    aggregate_news_sentiment,
    get_high_impact_news,
)
from twitter_monitor import (
    fetch_all_monitored_tweets,
    aggregate_twitter_sentiment,
    get_high_alert_tweets,
)
from signal_generator import generate_signal, FinalSignal
from discord_notifier import (
    send_signal_alert,
    send_price_alert,
    send_news_alert,
    send_twitter_alert,
    send_hourly_summary,
    send_startup_message,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("stock_bot.log"),
    ],
)
logger = logging.getLogger("main")


class StockBot:
    def __init__(self):
        self.last_market_scan = 0.0
        self.last_news_scan = 0.0
        self.last_twitter_scan = 0.0
        self.last_summary = 0.0

        # State
        self.previous_prices: dict[str, float] = {}
        self.latest_signals: list[FinalSignal] = []
        self.latest_news_sentiment: dict[str, float] = {}
        self.latest_twitter_sentiment: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Market scan
    # ------------------------------------------------------------------
    def run_market_scan(self) -> None:
        logger.info("Running market scan for %d tickers...", len(WATCHLIST))
        new_signals = []

        for ticker in WATCHLIST:
            tech = analyze_ticker(ticker)
            if tech is None:
                continue

            # Price alert
            if ticker in self.previous_prices:
                alert_msg = check_price_alert(
                    ticker,
                    self.previous_prices[ticker],
                    tech.price,
                    PRICE_MOVE_ALERT_PCT,
                )
                if alert_msg:
                    logger.info("PRICE ALERT: %s", alert_msg)
                    send_price_alert(alert_msg)

            self.previous_prices[ticker] = tech.price

            # Volume spike flag
            risk_flags = []
            if tech.volume_ratio >= VOLUME_SPIKE_MULTIPLIER:
                risk_flags.append(
                    f"Volume spike {tech.volume_ratio:.1f}x average — unusual activity"
                )

            news_sent = self.latest_news_sentiment.get(ticker, 0.0)
            twitter_sent = self.latest_twitter_sentiment.get(ticker, 0.0)

            signal = generate_signal(
                tech=tech,
                news_sentiment=news_sent,
                twitter_sentiment=twitter_sent,
                risk_flags=risk_flags,
            )
            new_signals.append(signal)

            # Only push to Discord if confidence is MEDIUM or HIGH
            if signal.confidence in ("MEDIUM", "HIGH"):
                logger.info("Signal: %s %s (score=%.2f)", ticker, signal.final_action, signal.composite_score)
                send_signal_alert(signal.as_discord_embed())

        self.latest_signals = new_signals
        logger.info("Market scan complete. %d signals generated.", len(new_signals))

    # ------------------------------------------------------------------
    # News scan
    # ------------------------------------------------------------------
    def run_news_scan(self) -> None:
        logger.info("Fetching news...")
        all_news = []
        all_news.extend(fetch_rss_news())
        all_news.extend(fetch_newsapi("stock market earnings fed"))

        # Per-ticker Finnhub news
        for ticker in WATCHLIST:
            if "-" not in ticker:   # Skip ETFs like BTC-USD for Finnhub
                all_news.extend(fetch_finnhub_news(ticker))

        self.latest_news_sentiment = aggregate_news_sentiment(all_news)

        high_impact = get_high_impact_news(all_news)
        logger.info("Found %d total news items, %d high-impact.", len(all_news), len(high_impact))

        for item in high_impact[:10]:  # Cap at 10 alerts per scan
            send_news_alert(
                title=item.title,
                summary=item.summary,
                url=item.url,
                source=item.source,
                sentiment=item.sentiment_score,
                tickers=item.tickers,
            )

    # ------------------------------------------------------------------
    # Twitter/X scan
    # ------------------------------------------------------------------
    def run_twitter_scan(self) -> None:
        logger.info("Scanning X/Twitter accounts...")
        tweets = fetch_all_monitored_tweets()
        self.latest_twitter_sentiment = aggregate_twitter_sentiment(tweets)

        high_alert = get_high_alert_tweets(tweets)
        logger.info("Fetched %d tweets, %d high-alert.", len(tweets), len(high_alert))

        for tw in high_alert[:8]:   # Cap alerts per scan
            send_twitter_alert(
                author=tw.author,
                text=tw.text,
                tier=tw.credibility_tier,
                tickers=tw.tickers,
                is_insider_risk=tw.is_insider_risk,
                alert_level=tw.alert_level,
            )

    # ------------------------------------------------------------------
    # Hourly summary
    # ------------------------------------------------------------------
    def run_hourly_summary(self) -> None:
        logger.info("Sending hourly summary...")
        all_sentiment_values = list(self.latest_news_sentiment.values()) + list(self.latest_twitter_sentiment.values())
        overall_sentiment = sum(all_sentiment_values) / len(all_sentiment_values) if all_sentiment_values else 0.0
        send_hourly_summary(self.latest_signals, overall_sentiment)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        logger.info("Stock Market Analysis Bot starting...")
        send_startup_message(WATCHLIST)

        while True:
            now = time.time()

            try:
                if now - self.last_news_scan >= NEWS_SCAN_INTERVAL:
                    self.run_news_scan()
                    self.last_news_scan = time.time()

                if now - self.last_twitter_scan >= TWITTER_SCAN_INTERVAL:
                    self.run_twitter_scan()
                    self.last_twitter_scan = time.time()

                if now - self.last_market_scan >= MARKET_SCAN_INTERVAL:
                    self.run_market_scan()
                    self.last_market_scan = time.time()

                if now - self.last_summary >= SUMMARY_INTERVAL:
                    self.run_hourly_summary()
                    self.last_summary = time.time()

            except KeyboardInterrupt:
                logger.info("Bot stopped by user.")
                break
            except Exception as exc:
                logger.exception("Unexpected error in main loop: %s", exc)

            # Sleep 30 seconds between loop ticks to stay responsive
            time.sleep(30)


if __name__ == "__main__":
    StockBot().run()
