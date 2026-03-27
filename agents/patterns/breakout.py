"""
Breakout Detector
-----------------
Detects price breakouts above resistance (bullish) or below support (bearish).

Algorithm
---------
1. Compute a rolling resistance level  = max(close, window=`resistance_window`)
   and a rolling support level         = min(close, window=`resistance_window`).
2. A bullish breakout occurs when the latest close exceeds the prior
   resistance level by at least `threshold` percent AND volume is above average.
3. A bearish breakout occurs when the latest close falls below the prior
   support level by at least `threshold` percent AND volume is above average.

Confidence is scored on:
    - Magnitude of the breakout relative to the ATR
    - Volume surge ratio (current volume vs. rolling average)
    - Candle body strength (close vs. open on the breakout bar)

Backtest
--------
Scans the full history for every breakout and measures the forward
return over `holding_bars` bars after the breakout bar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from agents.patterns.base import BacktestResult, PatternResult, PatternType


class BreakoutDetector:
    """
    Detects bullish and bearish price breakouts.

    Args:
        resistance_window: Lookback bars for resistance/support levels.
        threshold:         Minimum % move beyond the level to qualify.
        volume_window:     Lookback bars for average volume calculation.
        holding_bars:      Forward window (bars) used in the backtest.
    """

    def __init__(
        self,
        resistance_window: int = 20,
        threshold: float = 0.02,
        volume_window: int = 20,
        holding_bars: int = 10,
    ):
        self.resistance_window = resistance_window
        self.threshold = threshold
        self.volume_window = volume_window
        self.holding_bars = holding_bars

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def detect(self, df: pd.DataFrame) -> PatternResult:
        """
        Detect a breakout on the most recent bar.

        Args:
            df: OHLCV DataFrame with Close, Open, Volume columns.

        Returns:
            PatternResult — detected=True if a breakout is confirmed.
        """
        close  = df["Close"].squeeze()
        volume = df["Volume"].squeeze() if "Volume" in df.columns else None
        open_  = df["Open"].squeeze()   if "Open"   in df.columns else None

        result = self._check_latest(close, volume, open_)
        result.backtest = self._backtest(close, volume)
        return result

    # ------------------------------------------------------------------
    # Core detection
    # ------------------------------------------------------------------

    def _check_latest(
        self,
        close: pd.Series,
        volume: pd.Series | None,
        open_: pd.Series | None,
    ) -> PatternResult:
        """
        Evaluate the most recent bar for a breakout condition.

        Args:
            close:  Closing price series.
            volume: Volume series or None.
            open_:  Opening price series or None.

        Returns:
            PatternResult with detected flag, signal, and confidence.
        """
        if len(close) < self.resistance_window + 2:
            return self._no_pattern("Insufficient data for breakout detection.")

        # Levels are computed on the window BEFORE the current bar
        prior = close.iloc[-(self.resistance_window + 1): -1]
        resistance = float(prior.max())
        support    = float(prior.min())
        latest     = float(close.iloc[-1])

        # ATR for magnitude normalisation
        atr = self._atr(close)

        # Volume surge
        vol_ratio = self._volume_ratio(volume)

        # Candle body strength
        body_strength = self._body_strength(close, open_)

        # --- Bullish breakout ---
        if latest > resistance * (1 + self.threshold):
            magnitude = (latest - resistance) / (atr + 1e-9)
            confidence = self._confidence(magnitude, vol_ratio, body_strength, bullish=True)
            return PatternResult(
                pattern    = PatternType.BREAKOUT_BULLISH,
                detected   = True,
                confidence = confidence,
                signal     = "bullish",
                key_levels = {
                    "resistance": round(resistance, 4),
                    "support":    round(support, 4),
                    "latest":     round(latest, 4),
                    "atr":        round(atr, 4),
                },
                description = (
                    f"Bullish breakout: price {latest:.2f} broke above "
                    f"resistance {resistance:.2f} "
                    f"(+{(latest/resistance - 1)*100:.1f}%). "
                    f"Volume ratio: {vol_ratio:.2f}x average."
                ),
            )

        # --- Bearish breakout ---
        if latest < support * (1 - self.threshold):
            magnitude = (support - latest) / (atr + 1e-9)
            confidence = self._confidence(magnitude, vol_ratio, body_strength, bullish=False)
            return PatternResult(
                pattern    = PatternType.BREAKOUT_BEARISH,
                detected   = True,
                confidence = confidence,
                signal     = "bearish",
                key_levels = {
                    "resistance": round(resistance, 4),
                    "support":    round(support, 4),
                    "latest":     round(latest, 4),
                    "atr":        round(atr, 4),
                },
                description = (
                    f"Bearish breakout: price {latest:.2f} broke below "
                    f"support {support:.2f} "
                    f"({(latest/support - 1)*100:.1f}%). "
                    f"Volume ratio: {vol_ratio:.2f}x average."
                ),
            )

        return self._no_pattern(
            f"No breakout. Price {latest:.2f} within range "
            f"[{support:.2f}, {resistance:.2f}]."
        )

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    def _confidence(
        self,
        magnitude: float,
        vol_ratio: float,
        body_strength: float,
        bullish: bool,
    ) -> float:
        """
        Score breakout quality on three criteria.

        Criteria:
            1. Magnitude  — breakout size relative to ATR  (0–0.4)
            2. Volume     — volume surge above average      (0–0.4)
            3. Body       — candle body in breakout direction (0–0.2)

        Args:
            magnitude:     (price - level) / ATR.
            vol_ratio:     current_volume / avg_volume.
            body_strength: abs(close - open) / (high - low).
            bullish:       True for bullish breakout.

        Returns:
            Float between 0.0 and 1.0.
        """
        # 1. Magnitude score — cap at 3× ATR = full score
        mag_score = min(0.4, 0.4 * magnitude / 3.0)

        # 2. Volume score — 2× average = full score
        vol_score = min(0.4, 0.4 * (vol_ratio - 1.0) / 1.0) if vol_ratio > 1 else 0.0

        # 3. Body strength score
        body_score = min(0.2, 0.2 * body_strength)

        return round(min(1.0, mag_score + vol_score + body_score), 4)

    # ------------------------------------------------------------------
    # Backtest
    # ------------------------------------------------------------------

    def _backtest(
        self,
        close: pd.Series,
        volume: pd.Series | None,
    ) -> BacktestResult:
        """
        Scan the full price history for breakout occurrences and measure
        forward returns after each event.

        Args:
            close:  Full closing price series.
            volume: Volume series or None.

        Returns:
            BacktestResult with success_rate and avg_return.
        """
        occurrences = wins = 0
        returns: list[float] = []
        min_idx = self.resistance_window + 1

        for i in range(min_idx, len(close) - self.holding_bars):
            prior      = close.iloc[i - self.resistance_window: i]
            resistance = float(prior.max())
            support    = float(prior.min())
            current    = float(close.iloc[i])

            bullish_bo = current > resistance * (1 + self.threshold)
            bearish_bo = current < support    * (1 - self.threshold)

            if not (bullish_bo or bearish_bo):
                continue

            occurrences += 1
            entry  = current
            exit_  = float(close.iloc[i + self.holding_bars])
            fwd    = (exit_ - entry) / (entry + 1e-9)

            win = (bullish_bo and fwd > 0) or (bearish_bo and fwd < 0)
            if win:
                wins += 1
            returns.append(fwd if bullish_bo else -fwd)

        success_rate = wins / occurrences if occurrences else 0.0
        avg_return   = float(np.mean(returns)) if returns else 0.0

        return BacktestResult(
            occurrences  = occurrences,
            wins         = wins,
            success_rate = round(success_rate, 4),
            avg_return   = round(avg_return, 4),
            holding_bars = self.holding_bars,
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _atr(self, close: pd.Series, period: int = 14) -> float:
        """
        Approximate ATR using close-to-close range (no High/Low needed).

        Args:
            close:  Closing price series.
            period: ATR period.

        Returns:
            Average True Range as a float.
        """
        diff = close.diff().abs()
        return float(diff.rolling(period).mean().iloc[-1])

    def _volume_ratio(self, volume: pd.Series | None) -> float:
        """
        Compute current bar volume relative to rolling average.

        Args:
            volume: Volume series or None.

        Returns:
            Ratio float. Returns 1.0 if volume data is unavailable.
        """
        if volume is None or len(volume) < self.volume_window + 1:
            return 1.0
        avg = float(volume.iloc[-(self.volume_window + 1): -1].mean())
        cur = float(volume.iloc[-1])
        return cur / (avg + 1e-9)

    def _body_strength(
        self,
        close: pd.Series,
        open_: pd.Series | None,
    ) -> float:
        """
        Measure the candle body as a fraction of the recent price range.

        Args:
            close: Closing price series.
            open_: Opening price series or None.

        Returns:
            Float between 0.0 and 1.0.
        """
        if open_ is None:
            return 0.5
        body = abs(float(close.iloc[-1]) - float(open_.iloc[-1]))
        rng  = float(close.iloc[-20:].max() - close.iloc[-20:].min()) + 1e-9
        return min(1.0, body / rng)

    @staticmethod
    def _no_pattern(description: str) -> PatternResult:
        return PatternResult(
            pattern     = PatternType.NONE,
            detected    = False,
            confidence  = 0.0,
            signal      = "neutral",
            description = description,
        )
