"""
Market analyzer: fetches price data and computes technical indicators.
Produces a structured signal (LONG / SHORT / HOLD) per ticker.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class TechnicalSignal:
    ticker: str
    price: float
    change_pct: float
    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    sma_20: float
    sma_50: float
    sma_200: float
    volume: float
    avg_volume: float
    volume_ratio: float
    bb_upper: float
    bb_lower: float
    signal: str           # LONG / SHORT / HOLD
    score: float          # -1.0 (bearish) to +1.0 (bullish)
    reasons: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


def _calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("inf"))
    return 100 - (100 / (1 + rs))


def _calc_macd(series: pd.Series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _calc_bollinger(series: pd.Series, period=20, std_dev=2):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    return sma + std_dev * std, sma - std_dev * std


def analyze_ticker(ticker: str) -> Optional[TechnicalSignal]:
    """Download 6 months of daily data and compute all technicals."""
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=180)
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)

        if df.empty or len(df) < 50:
            logger.warning("Not enough data for %s", ticker)
            return None

        close = df["Close"].squeeze()
        volume = df["Volume"].squeeze()

        rsi = _calc_rsi(close)
        macd_line, signal_line, macd_hist = _calc_macd(close)
        bb_upper, bb_lower = _calc_bollinger(close)

        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()
        avg_vol = volume.rolling(20).mean()

        latest = close.iloc[-1]
        prev = close.iloc[-2]
        change_pct = (latest - prev) / prev * 100

        rsi_now = float(rsi.iloc[-1])
        macd_now = float(macd_line.iloc[-1])
        macd_sig = float(signal_line.iloc[-1])
        macd_h = float(macd_hist.iloc[-1])
        sma20_now = float(sma20.iloc[-1])
        sma50_now = float(sma50.iloc[-1])
        sma200_now = float(sma200.iloc[-1])
        vol_now = float(volume.iloc[-1])
        avg_vol_now = float(avg_vol.iloc[-1]) if float(avg_vol.iloc[-1]) > 0 else 1
        vol_ratio = vol_now / avg_vol_now
        bb_up = float(bb_upper.iloc[-1])
        bb_lo = float(bb_lower.iloc[-1])

        # --- Score each factor ---
        score = 0.0
        reasons = []

        # RSI
        if rsi_now < 30:
            score += 0.25
            reasons.append(f"RSI oversold ({rsi_now:.1f}) — potential reversal up")
        elif rsi_now > 70:
            score -= 0.25
            reasons.append(f"RSI overbought ({rsi_now:.1f}) — potential reversal down")
        elif rsi_now < 45:
            score += 0.10
            reasons.append(f"RSI bearish-neutral ({rsi_now:.1f})")
        elif rsi_now > 55:
            score -= 0.10
            reasons.append(f"RSI bullish-neutral ({rsi_now:.1f})")

        # MACD crossover
        prev_macd_h = float(macd_hist.iloc[-2])
        if macd_h > 0 and prev_macd_h <= 0:
            score += 0.20
            reasons.append("MACD bullish crossover")
        elif macd_h < 0 and prev_macd_h >= 0:
            score -= 0.20
            reasons.append("MACD bearish crossover")
        elif macd_h > 0:
            score += 0.08
            reasons.append(f"MACD positive histogram ({macd_h:.3f})")
        else:
            score -= 0.08
            reasons.append(f"MACD negative histogram ({macd_h:.3f})")

        # Moving average alignment
        if latest > sma20_now > sma50_now > sma200_now:
            score += 0.20
            reasons.append("Price above all MAs — strong uptrend")
        elif latest < sma20_now < sma50_now < sma200_now:
            score -= 0.20
            reasons.append("Price below all MAs — strong downtrend")
        elif latest > sma200_now:
            score += 0.08
            reasons.append("Price above 200 SMA — long-term uptrend")
        else:
            score -= 0.08
            reasons.append("Price below 200 SMA — long-term downtrend")

        # Golden/death cross (50 vs 200)
        prev_sma50 = float(sma50.iloc[-2])
        prev_sma200 = float(sma200.iloc[-2]) if len(sma200.dropna()) >= 2 else sma200_now
        if sma50_now > sma200_now and prev_sma50 <= prev_sma200:
            score += 0.15
            reasons.append("Golden cross (50 SMA crossed above 200 SMA)")
        elif sma50_now < sma200_now and prev_sma50 >= prev_sma200:
            score -= 0.15
            reasons.append("Death cross (50 SMA crossed below 200 SMA)")

        # Bollinger Bands
        if latest <= bb_lo:
            score += 0.10
            reasons.append("Price at/below lower Bollinger Band — oversold")
        elif latest >= bb_up:
            score -= 0.10
            reasons.append("Price at/above upper Bollinger Band — overbought")

        # Volume confirmation
        if vol_ratio > 2.5:
            volume_note = f"Volume spike {vol_ratio:.1f}x avg — confirms move"
            reasons.append(volume_note)
            score *= 1.15  # amplify conviction when high volume confirms direction

        # Clamp
        score = max(-1.0, min(1.0, score))

        # Translate to action
        if score >= 0.30:
            signal = "LONG"
        elif score <= -0.30:
            signal = "SHORT"
        else:
            signal = "HOLD"

        return TechnicalSignal(
            ticker=ticker,
            price=float(latest),
            change_pct=float(change_pct),
            rsi=rsi_now,
            macd=macd_now,
            macd_signal=macd_sig,
            macd_hist=macd_h,
            sma_20=sma20_now,
            sma_50=sma50_now,
            sma_200=sma200_now,
            volume=vol_now,
            avg_volume=avg_vol_now,
            volume_ratio=vol_ratio,
            bb_upper=bb_up,
            bb_lower=bb_lo,
            signal=signal,
            score=score,
            reasons=reasons,
        )

    except Exception as exc:
        logger.error("Failed to analyze %s: %s", ticker, exc)
        return None


def check_price_alert(ticker: str, previous_price: float, current_price: float,
                      threshold_pct: float = 2.0) -> Optional[str]:
    """Return an alert message if price moved beyond threshold."""
    if previous_price <= 0:
        return None
    pct = (current_price - previous_price) / previous_price * 100
    if abs(pct) >= threshold_pct:
        direction = "UP" if pct > 0 else "DOWN"
        return f"**{ticker}** price moved {direction} {abs(pct):.2f}% to ${current_price:.2f}"
    return None
