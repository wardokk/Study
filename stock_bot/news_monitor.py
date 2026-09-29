"""
News monitor: fetches from NewsAPI, RSS feeds, and Finnhub.
Runs sentiment analysis and flags high-impact market stories.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import hashlib

import feedparser
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config import NEWS_API_KEY, FINNHUB_API_KEY, NEWS_RSS_FEEDS, WATCHLIST

logger = logging.getLogger(__name__)
_vader = SentimentIntensityAnalyzer()

# Financial terms that amplify importance
HIGH_IMPACT_KEYWORDS = [
    "earnings", "fed", "federal reserve", "rate hike", "interest rate", "inflation",
    "gdp", "recession", "layoffs", "merger", "acquisition", "ipo", "bankruptcy",
    "sec investigation", "insider", "fraud", "guidance", "revenue beat", "miss",
    "buyback", "dividend", "short squeeze", "margin call", "crash", "rally",
    "circuit breaker", "tariff", "sanctions", "geopolitical", "war", "coup",
    "cpi", "ppi", "nfp", "fomc", "powell", "yellen", "ukraine", "china",
]

_seen_hashes: set[str] = set()


@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    source: str
    published: datetime
    tickers: list[str] = field(default_factory=list)
    sentiment_score: float = 0.0    # -1 bearish to +1 bullish
    impact_level: str = "LOW"       # LOW / MEDIUM / HIGH
    is_market_moving: bool = False


def _hash_article(title: str) -> str:
    return hashlib.md5(title.lower().strip().encode()).hexdigest()


def _score_sentiment(text: str) -> float:
    scores = _vader.polarity_scores(text)
    return scores["compound"]  # -1 to +1


def _detect_tickers(text: str) -> list[str]:
    text_upper = text.upper()
    return [t for t in WATCHLIST if t.replace("-USD", "") in text_upper]


def _assess_impact(title: str, summary: str) -> tuple[str, bool]:
    combined = (title + " " + summary).lower()
    hits = sum(1 for kw in HIGH_IMPACT_KEYWORDS if kw in combined)
    if hits >= 3:
        return "HIGH", True
    if hits >= 1:
        return "MEDIUM", False
    return "LOW", False


def fetch_rss_news() -> list[NewsItem]:
    items = []
    for feed_url in NEWS_RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                title = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")[:500]
                url = getattr(entry, "link", "")
                source = feed.feed.get("title", feed_url)

                h = _hash_article(title)
                if h in _seen_hashes:
                    continue
                _seen_hashes.add(h)

                published = datetime.utcnow()
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                    if datetime.utcnow() - published > timedelta(hours=6):
                        continue

                score = _score_sentiment(title + " " + summary)
                tickers = _detect_tickers(title + " " + summary)
                impact, moving = _assess_impact(title, summary)

                items.append(NewsItem(
                    title=title,
                    summary=summary,
                    url=url,
                    source=source,
                    published=published,
                    tickers=tickers,
                    sentiment_score=score,
                    impact_level=impact,
                    is_market_moving=moving,
                ))
        except Exception as exc:
            logger.warning("RSS feed error (%s): %s", feed_url, exc)
    return items


def fetch_newsapi(query: str = "stock market") -> list[NewsItem]:
    if not NEWS_API_KEY:
        return []
    try:
        since = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%S")
        params = {
            "q": query,
            "from": since,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": 20,
            "apiKey": NEWS_API_KEY,
            "domains": (
                "reuters.com,cnbc.com,wsj.com,bloomberg.com,"
                "ft.com,marketwatch.com,investing.com,seekingalpha.com"
            ),
        }
        resp = requests.get("https://newsapi.org/v2/everything", params=params, timeout=10)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        items = []
        for a in articles:
            title = a.get("title", "")
            summary = a.get("description", "") or ""
            url = a.get("url", "")
            source = a.get("source", {}).get("name", "NewsAPI")
            published_str = a.get("publishedAt", "")
            published = datetime.utcnow()
            try:
                published = datetime.strptime(published_str, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass

            h = _hash_article(title)
            if h in _seen_hashes:
                continue
            _seen_hashes.add(h)

            score = _score_sentiment(title + " " + summary)
            tickers = _detect_tickers(title + " " + summary)
            impact, moving = _assess_impact(title, summary)

            items.append(NewsItem(
                title=title, summary=summary[:500], url=url, source=source,
                published=published, tickers=tickers, sentiment_score=score,
                impact_level=impact, is_market_moving=moving,
            ))
        return items
    except Exception as exc:
        logger.error("NewsAPI error: %s", exc)
        return []


def fetch_finnhub_news(ticker: str) -> list[NewsItem]:
    if not FINNHUB_API_KEY:
        return []
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        url = "https://finnhub.io/api/v1/company-news"
        params = {"symbol": ticker, "from": yesterday, "to": today, "token": FINNHUB_API_KEY}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        items = []
        for a in resp.json()[:10]:
            title = a.get("headline", "")
            summary = a.get("summary", "")[:500]
            url_ = a.get("url", "")
            source = a.get("source", "Finnhub")
            published = datetime.utcfromtimestamp(a.get("datetime", time.time()))

            h = _hash_article(title)
            if h in _seen_hashes:
                continue
            _seen_hashes.add(h)

            score = _score_sentiment(title + " " + summary)
            impact, moving = _assess_impact(title, summary)

            items.append(NewsItem(
                title=title, summary=summary, url=url_, source=source,
                published=published, tickers=[ticker], sentiment_score=score,
                impact_level=impact, is_market_moving=moving,
            ))
        return items
    except Exception as exc:
        logger.error("Finnhub news error (%s): %s", ticker, exc)
        return []


def aggregate_news_sentiment(items: list[NewsItem]) -> dict[str, float]:
    """Average sentiment per ticker. Returns {ticker: avg_score}."""
    scores: dict[str, list[float]] = {}
    for item in items:
        for t in item.tickers:
            scores.setdefault(t, []).append(item.sentiment_score)
    return {t: sum(v) / len(v) for t, v in scores.items()}


def get_high_impact_news(items: list[NewsItem]) -> list[NewsItem]:
    return [i for i in items if i.impact_level in ("HIGH", "MEDIUM") or i.is_market_moving]
