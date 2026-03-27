"""
Pattern Detection — Shared Types
---------------------------------
All pattern detectors return a PatternResult so the QuantAgent
can handle every pattern through a single uniform interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class PatternType(str, Enum):
    HEAD_AND_SHOULDERS         = "head_and_shoulders"
    INVERSE_HEAD_AND_SHOULDERS = "inverse_head_and_shoulders"
    BREAKOUT_BULLISH           = "breakout_bullish"
    BREAKOUT_BEARISH           = "breakout_bearish"
    NONE                       = "none"


@dataclass
class PatternResult:
    """
    Standardised output for every pattern detector.

    Attributes:
        pattern:        Which pattern was detected (or NONE).
        detected:       True if the pattern is present in the latest data.
        confidence:     0.0–1.0 — how cleanly the pattern fits the criteria.
        signal:         'bullish', 'bearish', or 'neutral'.
        key_levels:     Dict of price levels relevant to the pattern
                        (e.g. neckline, resistance, support).
        description:    Human-readable explanation of what was found.
        backtest:       BacktestResult for this pattern type over history.
    """
    pattern:     PatternType
    detected:    bool
    confidence:  float                    # 0.0 – 1.0
    signal:      Literal["bullish", "bearish", "neutral"]
    key_levels:  dict[str, float]         = field(default_factory=dict)
    description: str                      = ""
    backtest:    "BacktestResult | None"  = None

    def to_dict(self) -> dict:
        return {
            "pattern":     self.pattern.value,
            "detected":    self.detected,
            "confidence":  round(self.confidence, 4),
            "signal":      self.signal,
            "key_levels":  {k: round(v, 4) for k, v in self.key_levels.items()},
            "description": self.description,
            "backtest":    self.backtest.to_dict() if self.backtest else None,
        }


@dataclass
class BacktestResult:
    """
    Historical success rate for a pattern type over the provided price series.

    Attributes:
        occurrences:   Total times the pattern was detected in history.
        wins:          Times the pattern led to the expected price move.
        success_rate:  wins / occurrences  (0.0 – 1.0).
        avg_return:    Average % return in the holding window after the pattern.
        holding_bars:  Number of bars used as the forward-return window.
    """
    occurrences:  int
    wins:         int
    success_rate: float
    avg_return:   float
    holding_bars: int

    def to_dict(self) -> dict:
        return {
            "occurrences":  self.occurrences,
            "wins":         self.wins,
            "success_rate": round(self.success_rate, 4),
            "avg_return":   round(self.avg_return, 4),
            "holding_bars": self.holding_bars,
        }
