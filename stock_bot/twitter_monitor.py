"""
Twitter/X monitor: tracks credible institutional accounts for market-moving signals.
Uses Twitter API v2 (Tweepy). Flags posts from regulatory bodies and top institutions
separately from opinion-based accounts.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config import TWITTER_BEARER_TOKEN, CREDIBLE_TWITTER_ACCOUNTS, WATCHLIST

logger = logging.getLogger(__name__)
_vader = SentimentIntensityAnalyzer()

# Regulatory / institutional accounts — highest credibility tier
REGULATORY_ACCOUNTS = {"federalreserve", "sec_news", "clevelandfed", "newyorkfed"}
INSTITUTIONAL_ACCOUNTS = {"goldmansachs", "jpmorgan", "bofa_news", "morganstanley",
                          "bloombergtv", "reutersbiz", "cnbcnow", "wsjmarkets", "ft", "markets"}
OPINION_ACCOUNTS = {"jimcramer", "elonmusk", "michaeljburry"}   # Notable but flagged as opinion


@dataclass
class Tweet:
    id: str
    author: str
    text: str
    published: datetime
    tickers: list[str] = field(default_factory=list)
    sentiment_score: float = 0.0
    credibility_tier: str = "OPINION"   # REGULATORY / INSTITUTIONAL / OPINION
    is_insider_risk: bool = False        # Anomalous specificity that may indicate early knowledge
    alert_level: str = "LOW"            # LOW / MEDIUM / HIGH


INSIDER_RISK_PATTERNS = [
    "expect", "will announce", "sources say", "breaking", "exclusive",
    "i hear", "rumor", "deal close", "merger talks", "acquisition target",
    "will report", "going private", "buyout", "take private", "leaked",
]

HIGH_FINANCIAL_KEYWORDS = [
    "rate cut", "rate hike", "fed decision", "earnings beat", "earnings miss",
    "sec charges", "sec investigation", "bankruptcy", "chapter 11",
    "short squeeze", "margin call", "acquisition", "merger", "ipo",
    "dividend cut", "buyback", "guidance raised", "guidance lowered",
]


def _detect_tickers(text: str) -> list[str]:
    text_upper = text.upper()
    return [t for t in WATCHLIST if t.replace("-USD", "") in text_upper
            or f"${t}" in text_upper]


def _score_insider_risk(text: str) -> bool:
    text_lower = text.lower()
    hits = sum(1 for kw in INSIDER_RISK_PATTERNS if kw in text_lower)
    fin_hits = sum(1 for kw in HIGH_FINANCIAL_KEYWORDS if kw in text_lower)
    return hits >= 1 and fin_hits >= 1


def _alert_level(tweet: Tweet) -> str:
    if tweet.credibility_tier == "REGULATORY":
        return "HIGH"
    if tweet.credibility_tier == "INSTITUTIONAL" and abs(tweet.sentiment_score) > 0.4:
        return "HIGH"
    if tweet.is_insider_risk:
        return "HIGH"
    if tweet.credibility_tier == "INSTITUTIONAL":
        return "MEDIUM"
    if abs(tweet.sentiment_score) > 0.6:
        return "MEDIUM"
    return "LOW"


def _get_credibility_tier(author: str) -> str:
    a = author.lower()
    if a in REGULATORY_ACCOUNTS:
        return "REGULATORY"
    if a in INSTITUTIONAL_ACCOUNTS:
        return "INSTITUTIONAL"
    return "OPINION"


def fetch_account_tweets(username: str, max_results: int = 10) -> list[Tweet]:
    """Fetch recent tweets from a single account via Twitter API v2."""
    if not TWITTER_BEARER_TOKEN:
        logger.debug("No Twitter bearer token configured — skipping @%s", username)
        return []

    try:
        import tweepy
        client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN, wait_on_rate_limit=False)

        user_resp = client.get_user(username=username, user_auth=False)
        if not user_resp.data:
            return []

        user_id = user_resp.data.id
        since = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()

        resp = client.get_users_tweets(
            id=user_id,
            max_results=max_results,
            start_time=since,
            tweet_fields=["created_at", "text"],
            user_auth=False,
        )

        tweets = []
        if not resp.data:
            return []

        for tw in resp.data:
            text = tw.text
            published = tw.created_at or datetime.now(timezone.utc)
            sentiment = _vader.polarity_scores(text)["compound"]
            tickers = _detect_tickers(text)
            tier = _get_credibility_tier(username)
            insider_risk = _score_insider_risk(text) and tier != "REGULATORY"

            t = Tweet(
                id=str(tw.id),
                author=username,
                text=text,
                published=published,
                tickers=tickers,
                sentiment_score=sentiment,
                credibility_tier=tier,
                is_insider_risk=insider_risk,
                alert_level="LOW",
            )
            t.alert_level = _alert_level(t)
            tweets.append(t)

        return tweets

    except ImportError:
        logger.error("tweepy not installed — pip install tweepy")
        return []
    except Exception as exc:
        logger.warning("Twitter fetch error (@%s): %s", username, exc)
        return []


def fetch_all_monitored_tweets() -> list[Tweet]:
    """Fetch tweets from all credible accounts in the watchlist."""
    all_tweets: list[Tweet] = []
    for account in CREDIBLE_TWITTER_ACCOUNTS:
        tweets = fetch_account_tweets(account)
        all_tweets.extend(tweets)
    return all_tweets


def get_high_alert_tweets(tweets: list[Tweet]) -> list[Tweet]:
    return [t for t in tweets if t.alert_level in ("HIGH", "MEDIUM")]


def aggregate_twitter_sentiment(tweets: list[Tweet]) -> dict[str, float]:
    """Average Twitter sentiment per ticker, weighted by credibility tier."""
    weights = {"REGULATORY": 3.0, "INSTITUTIONAL": 2.0, "OPINION": 0.5}
    scores: dict[str, list[float]] = {}
    for tw in tweets:
        w = weights.get(tw.credibility_tier, 1.0)
        for t in tw.tickers:
            scores.setdefault(t, []).append(tw.sentiment_score * w)
    return {t: sum(v) / len(v) for t, v in scores.items()}
