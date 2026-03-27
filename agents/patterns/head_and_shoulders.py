"""
Head & Shoulders Detector
--------------------------
Detects both regular (bearish) and inverse (bullish) H&S patterns
using local extrema on a closing price series.

Algorithm
---------
A valid H&S requires five pivot points in order:

    Regular (top):          left_shoulder > neckline
                            head > left_shoulder
                            right_shoulder ≈ left_shoulder  (within tolerance)
                            neckline is roughly flat

    Inverse (bottom):       mirror of the above on troughs

Confidence is scored on:
    - Shoulder symmetry  (how close right_shoulder ≈ left_shoulder)
    - Neckline flatness  (slope relative to price range)
    - Volume confirmation (volume declining from left shoulder → head → right shoulder)

Backtest
--------
Scans the full history for every H&S occurrence and measures the
forward return over `holding_bars` bars after the neckline break.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from agents.patterns.base import BacktestResult, PatternResult, PatternType


class HeadAndShouldersDetector:
    """
    Detects Head & Shoulders and Inverse Head & Shoulders patterns.

    Args:
        order:          Neighbourhood size for local extrema detection.
                        Higher = fewer, more significant pivots.
        sym_tolerance:  Max allowed relative difference between shoulder heights.
                        0.03 = shoulders must be within 3% of each other.
        holding_bars:   Forward window (bars) used in the backtest.
    """

    def __init__(
        self,
        order: int = 5,
        sym_tolerance: float = 0.05,
        holding_bars: int = 10,
    ):
        self.order = order
        self.sym_tolerance = sym_tolerance
        self.holding_bars = holding_bars

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def detect(self, df: pd.DataFrame) -> PatternResult:
        """
        Detect H&S or Inverse H&S in the most recent price window.

        Checks the last 60 bars for a valid pattern formation.

        Args:
            df: OHLCV DataFrame with a 'Close' column.

        Returns:
            PatternResult — detected=True if a valid pattern is found.
        """
        close = df["Close"].squeeze()
        volume = df["Volume"].squeeze() if "Volume" in df.columns else None

        # Scan recent window only for the live signal
        window = close.iloc[-60:]
        result = self._scan_window(window, volume, is_backtest=False)

        # Always attach a backtest over the full history
        result.backtest = self._backtest(close)
        return result

    # ------------------------------------------------------------------
    # Core detection
    # ------------------------------------------------------------------

    def _scan_window(
        self,
        close: pd.Series,
        volume: pd.Series | None,
        is_backtest: bool = False,
    ) -> PatternResult:
        """
        Scan a price series for the most recent valid H&S formation.

        Args:
            close:       Closing price series.
            volume:      Volume series (optional, used for confirmation).
            is_backtest: If True, suppress backtest attachment.

        Returns:
            PatternResult with detected flag and confidence.
        """
        peaks   = self._local_extrema(close, mode="max")
        troughs = self._local_extrema(close, mode="min")

        # --- Regular H&S (bearish) ---
        hs = self._find_hs(close, peaks, troughs, inverse=False)
        if hs:
            ls_idx, head_idx, rs_idx, nl_left, nl_right = hs
            confidence = self._confidence(
                close, ls_idx, head_idx, rs_idx, nl_left, nl_right,
                volume, inverse=False,
            )
            neckline = (close.iloc[nl_left] + close.iloc[nl_right]) / 2
            return PatternResult(
                pattern    = PatternType.HEAD_AND_SHOULDERS,
                detected   = True,
                confidence = confidence,
                signal     = "bearish",
                key_levels = {
                    "left_shoulder": round(float(close.iloc[ls_idx]), 4),
                    "head":          round(float(close.iloc[head_idx]), 4),
                    "right_shoulder":round(float(close.iloc[rs_idx]), 4),
                    "neckline":      round(float(neckline), 4),
                },
                description = (
                    f"Head & Shoulders detected. Neckline at {neckline:.2f}. "
                    f"A close below the neckline confirms the bearish reversal."
                ),
            )

        # --- Inverse H&S (bullish) ---
        ihs = self._find_hs(close, troughs, peaks, inverse=True)
        if ihs:
            ls_idx, head_idx, rs_idx, nl_left, nl_right = ihs
            confidence = self._confidence(
                close, ls_idx, head_idx, rs_idx, nl_left, nl_right,
                volume, inverse=True,
            )
            neckline = (close.iloc[nl_left] + close.iloc[nl_right]) / 2
            return PatternResult(
                pattern    = PatternType.INVERSE_HEAD_AND_SHOULDERS,
                detected   = True,
                confidence = confidence,
                signal     = "bullish",
                key_levels = {
                    "left_shoulder": round(float(close.iloc[ls_idx]), 4),
                    "head":          round(float(close.iloc[head_idx]), 4),
                    "right_shoulder":round(float(close.iloc[rs_idx]), 4),
                    "neckline":      round(float(neckline), 4),
                },
                description = (
                    f"Inverse Head & Shoulders detected. Neckline at {neckline:.2f}. "
                    f"A close above the neckline confirms the bullish reversal."
                ),
            )

        return PatternResult(
            pattern    = PatternType.NONE,
            detected   = False,
            confidence = 0.0,
            signal     = "neutral",
            description = "No Head & Shoulders pattern detected in the recent window.",
        )

    def _find_hs(
        self,
        close: pd.Series,
        primary: np.ndarray,    # peaks for H&S, troughs for inverse
        secondary: np.ndarray,  # troughs for H&S, peaks for inverse
        inverse: bool,
    ) -> tuple | None:
        """
        Search for a valid 5-pivot H&S sequence in the extrema arrays.

        Args:
            close:     Price series.
            primary:   Indices of the three main pivots (shoulders + head).
            secondary: Indices of the neckline pivots.
            inverse:   True for inverse H&S.

        Returns:
            Tuple (ls_idx, head_idx, rs_idx, nl_left_idx, nl_right_idx)
            or None if no valid pattern found.
        """
        if len(primary) < 3:
            return None

        # Try every combination of 3 consecutive primary pivots
        for i in range(len(primary) - 2):
            ls, head, rs = primary[i], primary[i + 1], primary[i + 2]
            ls_val, head_val, rs_val = (
                float(close.iloc[ls]),
                float(close.iloc[head]),
                float(close.iloc[rs]),
            )

            # Head must be the most extreme
            if not inverse:
                if not (head_val > ls_val and head_val > rs_val):
                    continue
            else:
                if not (head_val < ls_val and head_val < rs_val):
                    continue

            # Shoulder symmetry check
            sym = abs(ls_val - rs_val) / (abs(ls_val) + 1e-9)
            if sym > self.sym_tolerance:
                continue

            # Find neckline pivots between ls→head and head→rs
            nl_left_candidates  = secondary[(secondary > ls) & (secondary < head)]
            nl_right_candidates = secondary[(secondary > head) & (secondary < rs)]
            if len(nl_left_candidates) == 0 or len(nl_right_candidates) == 0:
                continue

            nl_left  = int(nl_left_candidates[-1])
            nl_right = int(nl_right_candidates[0])
            return ls, head, rs, nl_left, nl_right

        return None

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    def _confidence(
        self,
        close: pd.Series,
        ls: int, head: int, rs: int,
        nl_left: int, nl_right: int,
        volume: pd.Series | None,
        inverse: bool,
    ) -> float:
        """
        Score pattern quality on three criteria, each worth up to 1/3.

        Criteria:
            1. Shoulder symmetry  — closer = higher score
            2. Neckline flatness  — flatter = higher score
            3. Volume confirmation — declining volume left→head→right

        Args:
            close:   Price series.
            ls/head/rs: Pivot indices.
            nl_left/nl_right: Neckline pivot indices.
            volume:  Volume series or None.
            inverse: True for inverse H&S.

        Returns:
            Float between 0.0 and 1.0.
        """
        ls_val  = float(close.iloc[ls])
        rs_val  = float(close.iloc[rs])
        nl_l    = float(close.iloc[nl_left])
        nl_r    = float(close.iloc[nl_right])
        p_range = float(close.max() - close.min()) + 1e-9

        # 1. Shoulder symmetry (0–0.4)
        sym_diff = abs(ls_val - rs_val) / (abs(ls_val) + 1e-9)
        sym_score = max(0.0, 0.4 * (1 - sym_diff / self.sym_tolerance))

        # 2. Neckline flatness (0–0.4)
        neckline_slope = abs(nl_r - nl_l) / p_range
        flat_score = max(0.0, 0.4 * (1 - neckline_slope * 10))

        # 3. Volume confirmation (0–0.2)
        vol_score = 0.1  # neutral if no volume data
        if volume is not None:
            try:
                v_ls   = float(volume.iloc[ls])
                v_head = float(volume.iloc[head])
                v_rs   = float(volume.iloc[rs])
                if not inverse:
                    # Classic H&S: volume should decrease ls > head > rs
                    if v_ls > v_head > v_rs:
                        vol_score = 0.2
                    elif v_ls > v_rs:
                        vol_score = 0.1
                else:
                    # Inverse: volume should increase on the right shoulder breakout
                    if v_rs > v_head:
                        vol_score = 0.2
                    else:
                        vol_score = 0.1
            except Exception:
                pass

        return round(min(1.0, sym_score + flat_score + vol_score), 4)

    # ------------------------------------------------------------------
    # Backtest
    # ------------------------------------------------------------------

    def _backtest(self, close: pd.Series) -> BacktestResult:
        """
        Scan the full price history for H&S occurrences and measure
        forward returns after each neckline break.

        Args:
            close: Full closing price series.

        Returns:
            BacktestResult with success_rate and avg_return.
        """
        occurrences = wins = 0
        returns: list[float] = []

        step = max(1, self.order * 2)
        for end in range(60, len(close) - self.holding_bars, step):
            window = close.iloc[end - 60: end]
            peaks   = self._local_extrema(window, "max")
            troughs = self._local_extrema(window, "min")

            found = self._find_hs(window, peaks, troughs, inverse=False)
            if not found:
                found = self._find_hs(window, troughs, peaks, inverse=True)
                is_inverse = True
            else:
                is_inverse = False

            if found:
                occurrences += 1
                _, _, _, nl_left, nl_right = found
                neckline = (float(window.iloc[nl_left]) + float(window.iloc[nl_right])) / 2
                entry = float(close.iloc[end])
                exit_ = float(close.iloc[min(end + self.holding_bars, len(close) - 1)])
                fwd_return = (exit_ - entry) / (entry + 1e-9)

                # Win = price moved in the expected direction
                if is_inverse:
                    win = fwd_return > 0
                else:
                    win = fwd_return < 0

                if win:
                    wins += 1
                returns.append(fwd_return if is_inverse else -fwd_return)

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

    def _local_extrema(self, series: pd.Series, mode: str) -> np.ndarray:
        """
        Find indices of local maxima or minima in a price series.

        Args:
            series: Price series.
            mode:   'max' for peaks, 'min' for troughs.

        Returns:
            Sorted numpy array of integer indices.
        """
        arr = series.values
        if mode == "max":
            idx = argrelextrema(arr, np.greater_equal, order=self.order)[0]
        else:
            idx = argrelextrema(arr, np.less_equal, order=self.order)[0]
        return idx
