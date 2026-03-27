from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class AgentResult:
    """Standardized result container for all agents."""

    def __init__(self, agent_name: str, data: dict, score: float | None = None, error: str | None = None):
        self.agent_name = agent_name
        self.data = data
        self.score = score          # normalized 0.0–1.0 signal score
        self.error = error
        self.success = error is None

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "success": self.success,
            "score": self.score,
            "data": self.data,
            "error": self.error,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all Zenith IQ agents.
    Every agent must implement `run()` and return an AgentResult.
    """

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def run(self, ticker: str, **kwargs: Any) -> AgentResult:
        """
        Execute the agent's analysis for a given ticker.

        Args:
            ticker: Stock ticker symbol (e.g. 'AAPL')
            **kwargs: Agent-specific optional parameters

        Returns:
            AgentResult with data and normalized score
        """
        pass

    def _safe_run(self, func, *args, fallback=None, **kwargs):
        """Utility wrapper to catch and log exceptions without crashing."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"[{self.name}] Error: {e}")
            return fallback

    def __repr__(self) -> str:
        return f"<Agent:{self.name}>"
