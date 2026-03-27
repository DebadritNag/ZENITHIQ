"""
Pattern detection sub-package.
Exposes all detectors and the shared PatternResult type.
"""

from agents.patterns.base import PatternResult, PatternType
from agents.patterns.head_and_shoulders import HeadAndShouldersDetector
from agents.patterns.breakout import BreakoutDetector

__all__ = [
    "PatternResult",
    "PatternType",
    "HeadAndShouldersDetector",
    "BreakoutDetector",
]
