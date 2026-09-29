"""
Configuration for the Stock Market Analysis Bot.
All API keys and settings are loaded from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_ALERT_WEBHOOK_URL = os.getenv("DISCORD_ALERT_WEBHOOK_URL", DISCORD_WEBHOOK_URL)

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

# Twitter/X API v2
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

# --- Watchlist ---
# Stocks to monitor continuously
WATCHLIST = [
    "AAPL",   # Apple
    "NVDA",   # NVIDIA
    "MSFT",   # Microsoft
    "GOOGL",  # Alphabet
    "AMZN",   # Amazon
    "TSLA",   # Tesla
    "META",   # Meta
    "SPY",    # S&P 500 ETF
    "QQQ",    # Nasdaq ETF
    "BTC-USD", # Bitcoin
]

# --- Scan Intervals (seconds) ---
MARKET_SCAN_INTERVAL = 300       # Price & technical scan every 5 minutes
NEWS_SCAN_INTERVAL = 600         # News scan every 10 minutes
TWITTER_SCAN_INTERVAL = 900      # Twitter scan every 15 minutes
SUMMARY_INTERVAL = 3600          # Full summary report every 1 hour

# --- Alert Thresholds ---
PRICE_MOVE_ALERT_PCT = 2.0       # Alert if price moves > 2% in one interval
VOLUME_SPIKE_MULTIPLIER = 2.5    # Alert if volume > 2.5x average
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30

# --- Credible Twitter/X Accounts to Monitor ---
# Only verified institutional/regulatory/top-analyst accounts
CREDIBLE_TWITTER_ACCOUNTS = [
    "federalreserve",     # Federal Reserve
    "SEC_News",           # SEC official
    "BloombergTV",        # Bloomberg
    "ReutersBiz",         # Reuters Business
    "CNBCnow",            # CNBC
    "WSJmarkets",         # Wall Street Journal Markets
    "FT",                 # Financial Times
    "markets",            # Bloomberg Markets
    "GoldmanSachs",       # Goldman Sachs
    "jpmorgan",           # JP Morgan
    "BofA_News",          # Bank of America
    "MorganStanley",      # Morgan Stanley
    "ClevelandFed",       # Cleveland Federal Reserve
    "NewYorkFed",         # New York Fed
    "jimcramer",          # Jim Cramer (notable, flag as opinion)
    "elonmusk",           # Elon Musk (market moving)
    "michaeljburry",      # Michael Burry
]

# --- Reliable News RSS Sources ---
NEWS_RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/technologyNews",
    "https://feeds.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.wsj.com/xml/rss/3_7031.xml",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://finance.yahoo.com/news/rssindex",
    "https://www.marketwatch.com/rss/topstories",
    "https://seekingalpha.com/market_currents.xml",
    "https://feeds.ft.com/rss/home/us",
    "https://www.investing.com/rss/news_25.rss",
]

# --- Signal weights for final recommendation ---
# Weights must sum to 1.0
SIGNAL_WEIGHTS = {
    "technical": 0.45,    # RSI, MACD, MA crossovers, volume
    "sentiment": 0.30,    # News + Twitter sentiment
    "momentum":  0.25,    # Price momentum
}
