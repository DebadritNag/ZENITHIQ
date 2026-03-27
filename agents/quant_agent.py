"""
Quant Agent
-----------
Fetches OHLCV data, runs pattern detection (Head & Shoulders, Breakout),
computes technical indicators (RSI, MACD, Bollinger Bands, MA Cross),
backtests each pattern over the full history, and combines everything
into a single 0–1 Alpha Score.

Output per pattern
------------------
    {
        "pattern":      "breakout_bullish",
        "detected":     true,
        "confidence":   0.74,
        "signal":       "bullish",
        "key_levels":   { "resistance": 182.5, "support": 174.1, ... },
        "description":  "Bullish breakout: price 185.3 broke above ...",
        "backtest": {
            "occurrences":  12,
            "wins":         8,
            "success_rate": 0.6667,
            "avg_return":   0.0231,
            "holding_bars": 10
        }
    }
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any

from agents.base_agent import BaseAgent, AgentResult
from agents.patterns import (
    HeadAndShouldersDetector,
    BreakoutDetector,
    PatternResult,
    PatternType,
)
from data_pipeline import fetch_stock_snapshot, StockSnapshot


class QuantAgent(BaseAgent):
    """
    Technical analysis, pattern detection, and backtesting agent.

    Workflow:
        1. Fetch OHLCV data via the data pipeline.
        2. Detect Head & Shoulders and Breakout patterns.
        3. Compute RSI, MACD, Bollinger Bands, and MA cross indicators.
        4. Backtest each pattern over the full price history.
        5. Combine all signals into a 0–1 quant score.
    """

    def __init__(self):
        super().__init__("QuantAgent")
        self._hs_detector = HeadAndShouldersDetector(
            order=5,
            sym_tolerance=0.05,
            holding_bars=10,
        )
        self._bo_detector = BreakoutDetector(
            resistance_window=20,
            threshold=0.02,
            volume_window=20,
            holding_bars=10,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self, ticker: str, **kwargs: Any) -> AgentResult:
        """
        Run full quant analysis for `ticker`.

        Args:
            ticker: Stock ticker symbol.
            period: yfinance period string (default '1y').
                    Use at least '1y' for meaningful backtests.

        Returns:
            AgentResult with patterns, indicators, backtest stats, and 0–1 score.
        """
        period = kwargs.get("period", "1y")

        try:
            snapshot = fetch_stock_snapshot(ticker, period=period)
            df = self._to_df(snapshot)

            if df.empty or len(df) < 30:
                return AgentResult(
                    self.name, {"message": "Insufficient price data"}, score=0.5
                )

            # --- Pattern detection (includes per-pattern backtest) ---
            hs_result = self._hs_detector.detect(df)
            bo_result = self._bo_detector.detect(df)

            # --- Technical indicators ---
            indicators = self._compute_indicators(df)

            # --- Composite score ---
            score = self._score(hs_result, bo_result, indicators)

            return AgentResult(
                self.name,
                {
                    "patterns": {
                        "head_and_shoulders": hs_result.to_dict(),
                        "breakout":           bo_result.to_dict(),
                    },
                    "indicators": indicators,
                    "bar_count":  len(df),
                    "period":     period,
                },
                score=score,
            )

        except Exception as exc:
            self.logger.error(f"QuantAgent failed for {ticker}: {exc}")
            return AgentResult(self.name, {}, score=0.5, error=str(exc))

    # ------------------------------------------------------------------
    # DataFrame conversion
    # ------------------------------------------------------------------

    def _to_df(self, snapshot: StockSnapshot) -> pd.DataFrame:
        """
        Convert a StockSnapshot into a pandas DataFrame.

        Args:
            snapshot: StockSnapshot from the data pipeline.

        Returns:
            DataFrame indexed by date with OHLCV columns.
        """
        if not snapshot.bars:
            return pd.DataFrame()
        df = pd.DataFrame([b.__dict__ for b in snapshot.bars])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").rename(columns={
            "open": "Open", "high": "High",
            "low": "Low", "close": "Close", "volume": "Volume",
        })
        return df.dropna()

    # ------------------------------------------------------------------
    # Technical indicators
    # ------------------------------------------------------------------

    def _compute_indicators(self, df: pd.DataFrame) -> dict:
        """
        Compute RSI, MACD, Bollinger Bands, and MA cross signals.

        Args:
            df: OHLCV DataFrame.

        Returns:
            Dict of latest indicator values and signal flags.
        """
        close = df["Close"].squeeze()

        # RSI (14)
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rs    = gain / loss.replace(0, np.nan)
        rsi   = 100 - (100 / (1 + rs))
        latest_rsi = float(rsi.iloc[-1])

        # MACD (12, 26, 9)
        ema12       = close.ewm(span=12, adjust=False).mean()
        ema26       = close.ewm(span=26, adjust=False).mean()
        macd_line   = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist   = macd_line - signal_line
        macd_bullish = bool(macd_hist.iloc[-1] > 0)
        macd_cross   = bool(
            macd_hist.iloc[-1] > 0 and macd_hist.iloc[-2] <= 0
        )  # fresh bullish crossover

        # Bollinger Bands (20, 2σ)
        sma20      = close.rolling(20).mean()
        std20      = close.rolling(20).std()
        upper_band = sma20 + 2 * std20
        lower_band = sma20 - 2 * std20
        latest_close = float(close.iloc[-1])
        bb_position  = float(
            (latest_close - float(lower_band.iloc[-1])) /
            (float(upper_band.iloc[-1]) - float(lower_band.iloc[-1]) + 1e-9)
        )

        # Golden / Death Cross (50 vs 200 SMA)
        sma50  = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()
        golden_cross = (
            bool(sma50.iloc[-1] > sma200.iloc[-1])
            if len(close) >= 200 else None
        )

        return {
            "rsi":          round(latest_rsi, 2),
            "rsi_signal":   (
                "oversold"   if latest_rsi < 30 else
                "overbought" if latest_rsi > 70 else
                "neutral"
            ),
            "macd_bullish":  macd_bullish,
            "macd_cross":    macd_cross,
            "bb_position":   round(bb_position, 4),
            "golden_cross":  golden_cross,
            "latest_close":  round(latest_close, 4),
        }

    # ------------------------------------------------------------------
    # Composite scoring
    # ------------------------------------------------------------------

    def _score(
        self,
        hs: PatternResult,
        bo: PatternResult,
        indicators: dict,
    ) -> float:
        """
        Combine pattern signals, backtest success rates, and indicators
        into a single 0–1 quant score.

        Scoring breakdown (max 1.0):
            Pattern signals    — up to 0.40
            Backtest quality   — up to 0.20
            Technical indicators — up to 0.40

        Args:
            hs:         Head & Shoulders PatternResult.
            bo:         Breakout PatternResult.
            indicators: Output of _compute_indicators().

        Returns:
            Float clamped to [0.0, 1.0].
        """
        score = 0.5

        # ---- Pattern contribution (±0.20 each) ----
        for pattern in (hs, bo):
            if not pattern.detected:
                continue
            direction = 1.0 if pattern.signal == "bullish" else -1.0
            score += direction * 0.20 * pattern.confidence

        # ---- Backtest quality bonus (up to +0.10 per pattern) ----
        for pattern in (hs, bo):
            if pattern.detected and pattern.backtest:
                bt = pattern.backtest
                if bt.occurrences >= 3 and bt.success_rate > 0.55:
                    direction = 1.0 if pattern.signal == "bullish" else -1.0
                    score += direction * 0.10 * bt.success_rate

        # ---- Technical indicators (up to ±0.40 total) ----
        rsi_sig = indicators.get("rsi_signal")
        if rsi_sig == "oversold":
            score += 0.10
        elif rsi_sig == "overbought":
            score -= 0.10

        if indicators.get("macd_bullish"):
            score += 0.08
        if indicators.get("macd_cross"):        # fresh crossover = stronger signal
            score += 0.05

        bb_pos = indicators.get("bb_position", 0.5)
        if bb_pos < 0.20:                       # near lower band → oversold
            score += 0.07
        elif bb_pos > 0.80:                     # near upper band → overbought
            score -= 0.07

        if indicators.get("golden_cross") is True:
            score += 0.10
        elif indicators.get("golden_cross") is False:
            score -= 0.08

        return round(float(np.clip(score, 0.0, 1.0)), 4)
