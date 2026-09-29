"""
Signal generator: combines technical, news, and Twitter signals into a final
weighted recommendation (LONG / SHORT / HOLD) with a confidence score.
"""

from dataclasses import dataclass, field
from datetime import datetime

from config import SIGNAL_WEIGHTS
from market_analyzer import TechnicalSignal


@dataclass
class FinalSignal:
    ticker: str
    price: float
    change_pct: float
    final_action: str           # LONG / SHORT / HOLD
    confidence: str             # LOW / MEDIUM / HIGH
    composite_score: float      # -1 to +1
    technical_score: float
    sentiment_score: float
    momentum_score: float
    technical_reasons: list[str] = field(default_factory=list)
    news_headlines: list[str] = field(default_factory=list)
    twitter_notes: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def as_discord_embed(self) -> dict:
        """Format for a Discord embed payload."""
        action_color = {
            "LONG": 0x00FF7F,    # green
            "SHORT": 0xFF4444,   # red
            "HOLD": 0xFFAA00,    # amber
        }.get(self.final_action, 0x888888)

        confidence_emoji = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "⚠️"}.get(self.confidence, "")
        action_emoji = {"LONG": "📈", "SHORT": "📉", "HOLD": "⏸️"}.get(self.final_action, "")

        change_arrow = "▲" if self.change_pct >= 0 else "▼"
        change_color = "+" if self.change_pct >= 0 else ""

        fields = [
            {"name": "Price", "value": f"${self.price:.2f}  {change_arrow} {change_color}{self.change_pct:.2f}%", "inline": True},
            {"name": "Composite Score", "value": f"{self.composite_score:+.2f}", "inline": True},
            {"name": "Confidence", "value": f"{self.confidence} {confidence_emoji}", "inline": True},
            {"name": "Technical Score", "value": f"{self.technical_score:+.2f}", "inline": True},
            {"name": "Sentiment Score", "value": f"{self.sentiment_score:+.2f}", "inline": True},
            {"name": "Momentum Score", "value": f"{self.momentum_score:+.2f}", "inline": True},
        ]

        if self.technical_reasons:
            fields.append({
                "name": "📊 Technical Signals",
                "value": "\n".join(f"• {r}" for r in self.technical_reasons[:5]),
                "inline": False,
            })

        if self.news_headlines:
            fields.append({
                "name": "📰 Key News",
                "value": "\n".join(f"• {h}" for h in self.news_headlines[:3]),
                "inline": False,
            })

        if self.twitter_notes:
            fields.append({
                "name": "🐦 X / Twitter",
                "value": "\n".join(f"• {n}" for n in self.twitter_notes[:3]),
                "inline": False,
            })

        if self.risk_flags:
            fields.append({
                "name": "🚨 Risk Flags",
                "value": "\n".join(f"• {f}" for f in self.risk_flags),
                "inline": False,
            })

        return {
            "embeds": [{
                "title": f"{action_emoji} {self.ticker} — **{self.final_action}** {action_emoji}",
                "color": action_color,
                "fields": fields,
                "footer": {"text": f"Stock Analysis Bot • {self.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"},
            }]
        }


def generate_signal(
    tech: TechnicalSignal,
    news_sentiment: float = 0.0,
    twitter_sentiment: float = 0.0,
    news_headlines: list[str] | None = None,
    twitter_notes: list[str] | None = None,
    risk_flags: list[str] | None = None,
) -> FinalSignal:
    """Combine all sub-signals into a single weighted recommendation."""

    # Momentum score from recent price action
    momentum = tech.change_pct / 10.0   # Normalise: 10% move = score of 1.0
    momentum = max(-1.0, min(1.0, momentum))

    w = SIGNAL_WEIGHTS
    composite = (
        w["technical"] * tech.score
        + w["sentiment"] * (news_sentiment * 0.6 + twitter_sentiment * 0.4)
        + w["momentum"] * momentum
    )
    composite = max(-1.0, min(1.0, composite))

    # Action
    if composite >= 0.25:
        action = "LONG"
    elif composite <= -0.25:
        action = "SHORT"
    else:
        action = "HOLD"

    # Confidence based on |composite| and agreement between sub-signals
    sub_signs = [
        1 if tech.score > 0 else (-1 if tech.score < 0 else 0),
        1 if news_sentiment > 0 else (-1 if news_sentiment < 0 else 0),
        1 if twitter_sentiment > 0 else (-1 if twitter_sentiment < 0 else 0),
        1 if momentum > 0 else (-1 if momentum < 0 else 0),
    ]
    agreement = sum(1 for s in sub_signs if s != 0 and s == sub_signs[0]) / max(1, len([s for s in sub_signs if s != 0]))

    if abs(composite) >= 0.55 and agreement >= 0.75:
        confidence = "HIGH"
    elif abs(composite) >= 0.30 and agreement >= 0.50:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return FinalSignal(
        ticker=tech.ticker,
        price=tech.price,
        change_pct=tech.change_pct,
        final_action=action,
        confidence=confidence,
        composite_score=round(composite, 3),
        technical_score=round(tech.score, 3),
        sentiment_score=round(news_sentiment * 0.6 + twitter_sentiment * 0.4, 3),
        momentum_score=round(momentum, 3),
        technical_reasons=tech.reasons,
        news_headlines=news_headlines or [],
        twitter_notes=twitter_notes or [],
        risk_flags=risk_flags or [],
    )
