"""
Sentiment Agent
---------------
Uses cardiffnlp/twitter-roberta-base-sentiment for social media
sentiment analysis with batch inference for fast throughput.

Primary data source: get_mock_posts() from data_pipeline.mock_data.
Live Reddit scraping is attempted first; mock data is used when
scraping is unavailable or returns nothing.

Model labels:  LABEL_0 = negative, LABEL_1 = neutral, LABEL_2 = positive
Output score:  float in [-1.0, +1.0]
Output label:  'positive' | 'neutral' | 'negative'
"""

import re
import requests
import numpy as np
from typing import Any

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from agents.base_agent import BaseAgent, AgentResult
from data_pipeline.mock_data import get_mock_posts


MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"

# Maps model output indices → human labels and [-1, +1] weights
_LABEL_MAP = {
    "LABEL_0": ("negative", -1.0),
    "LABEL_1": ("neutral",   0.0),
    "LABEL_2": ("positive",  1.0),
}

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"


class SentimentAgent(BaseAgent):
    """
    Batch social-media sentiment analyser using RoBERTa.

    The model is lazy-loaded on first inference call so startup
    cost is deferred until the agent is actually used.

    Public API:
        score_posts(posts)  →  list[SentimentResult]
        run(ticker)         →  AgentResult  (coordinator interface)
    """

    # Shared across all instances — loaded once per process
    _tokenizer: AutoTokenizer | None = None
    _model: AutoModelForSequenceClassification | None = None

    def __init__(self, batch_size: int = 32):
        """
        Args:
            batch_size: Number of texts processed per forward pass.
                        32 is a good default for CPU; raise to 64+ on GPU.
        """
        super().__init__("SentimentAgent")
        self.batch_size = batch_size
        self._device = "cuda" if torch.cuda.is_available() else "cpu"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def score_posts(self, posts: list[str]) -> list[dict]:
        """
        Score a list of social media posts in batches.

        Args:
            posts: Raw text strings (tweets, Reddit titles, etc.).

        Returns:
            List of dicts, one per input post:
            {
                "text":  str,           # truncated to 80 chars
                "label": str,           # 'positive' | 'neutral' | 'negative'
                "score": float,         # model confidence [0, 1]
                "sentiment": float,     # mapped to [-1.0, +1.0]
            }
        """
        if not posts:
            return []

        tokenizer, model = self._load_model()
        cleaned = [self._preprocess(p) for p in posts]
        results: list[dict] = []

        for batch_start in range(0, len(cleaned), self.batch_size):
            batch = cleaned[batch_start: batch_start + self.batch_size]
            raw_posts = posts[batch_start: batch_start + self.batch_size]
            batch_results = self._infer_batch(batch, raw_posts, tokenizer, model)
            results.extend(batch_results)

        return results

    def aggregate(self, scored: list[dict]) -> tuple[float, str]:
        """
        Reduce per-post scores to a single sentiment score and label.

        Uses confidence-weighted average of the [-1, +1] sentiment values.

        Args:
            scored: Output of score_posts().

        Returns:
            Tuple of (sentiment_score: float[-1, +1], label: str).
        """
        if not scored:
            return 0.0, "neutral"

        weights = np.array([s["score"] for s in scored], dtype=np.float32)
        values  = np.array([s["sentiment"] for s in scored], dtype=np.float32)

        total_weight = weights.sum()
        if total_weight == 0:
            return 0.0, "neutral"

        agg_score = float(np.dot(weights, values) / total_weight)
        agg_score = round(np.clip(agg_score, -1.0, 1.0).item(), 4)

        if agg_score > 0.15:
            label = "positive"
        elif agg_score < -0.15:
            label = "negative"
        else:
            label = "neutral"

        return agg_score, label

    async def run(self, ticker: str, **kwargs: Any) -> AgentResult:
        """
        Coordinator interface: score social media posts for `ticker`.

        Data source priority:
            1. `posts` kwarg — caller-supplied list (highest priority)
            2. Mock data via get_mock_posts()  ← primary source
            3. Live Reddit scrape              ← attempted only if mock disabled

        Args:
            ticker:       Stock ticker symbol.
            max_posts:    Max posts to score (default 40).
            posts:        Optional pre-supplied list[str].
            use_mock:     Force mock data even if Reddit is available (default True).

        Returns:
            AgentResult with:
                post_count      — number of posts scored
                sentiment_score — weighted average [-1, +1]
                label           — 'positive' | 'neutral' | 'negative'
                sample_scores   — first 5 per-post results
            score (0–1) normalised for coordinator weighted average.
        """
        max_posts = kwargs.get("max_posts", 40)
        use_mock  = kwargs.get("use_mock", True)
        posts: list[str] = list(kwargs.get("posts") or [])

        try:
            # 1. Caller-supplied posts take priority
            if not posts:
                if use_mock:
                    # Primary: mock social media data
                    posts = get_mock_posts(ticker, count=max_posts)
                    self.logger.info(f"[SentimentAgent] Using mock posts for {ticker} ({len(posts)} posts)")
                else:
                    # Attempt live Reddit scrape
                    posts = self._fetch_reddit_posts(ticker, max_posts)
                    if not posts:
                        self.logger.info(f"[SentimentAgent] Reddit empty for {ticker}, falling back to mock")
                        posts = get_mock_posts(ticker, count=max_posts)

            if not posts:
                return AgentResult(self.name, {"message": "No posts available"}, score=0.5)

            scored = self.score_posts(posts)
            sentiment_score, label = self.aggregate(scored)

            # Normalise [-1, +1] → [0, 1] for coordinator compatibility
            normalised = round((sentiment_score + 1.0) / 2.0, 4)

            return AgentResult(
                self.name,
                {
                    "post_count":      len(posts),
                    "sentiment_score": sentiment_score,   # raw [-1, +1]
                    "label":           label,
                    "sample_scores":   scored[:5],
                },
                score=normalised,
            )

        except Exception as exc:
            self.logger.error(f"SentimentAgent failed for {ticker}: {exc}")
            return AgentResult(self.name, {}, score=0.5, error=str(exc))

    def analyse_mock(self, symbol: str, count: int = 18) -> dict:
        """
        Convenience method: run the full mock → score → aggregate pipeline
        and return a clean result dict.

        Useful for direct calls outside the coordinator (e.g. API endpoints,
        tests, or the Zenith dashboard).

        Args:
            symbol: Stock ticker symbol.
            count:  Number of mock posts to generate (default 18).

        Returns:
            {
                "score": float,   # weighted average sentiment [-1, +1]
                "label": str,     # 'positive' | 'neutral' | 'negative'
            }
        """
        posts  = get_mock_posts(symbol, count=count)
        scored = self.score_posts(posts)
        sentiment_score, label = self.aggregate(scored)
        return {"score": sentiment_score, "label": label}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(
        self,
    ) -> tuple[AutoTokenizer, AutoModelForSequenceClassification]:
        """
        Lazy-load tokenizer and model into class-level cache.
        Thread-safe for single-process use (FastAPI default).

        Returns:
            Tuple of (tokenizer, model) ready for inference.
        """
        if SentimentAgent._tokenizer is None:
            self.logger.info(f"Loading {MODEL_NAME} onto {self._device}...")
            SentimentAgent._tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            SentimentAgent._model = (
                AutoModelForSequenceClassification
                .from_pretrained(MODEL_NAME)
                .to(self._device)
                .eval()
            )
            self.logger.info("Model loaded.")
        return SentimentAgent._tokenizer, SentimentAgent._model

    def _preprocess(self, text: str) -> str:
        """
        Clean text for RoBERTa: replace URLs and @mentions with tokens,
        collapse whitespace, and truncate to 128 chars (well within 512 tokens).

        Args:
            text: Raw social media post string.

        Returns:
            Cleaned string.
        """
        text = re.sub(r"http\S+", "http", text)
        text = re.sub(r"@\w+", "@user", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:512]

    def _infer_batch(
        self,
        cleaned_texts: list[str],
        raw_texts: list[str],
        tokenizer: AutoTokenizer,
        model: AutoModelForSequenceClassification,
    ) -> list[dict]:
        """
        Run a single batched forward pass and decode results.

        Args:
            cleaned_texts: Pre-processed text strings for the model.
            raw_texts:     Original texts (used for display only).
            tokenizer:     Loaded tokenizer.
            model:         Loaded model in eval mode.

        Returns:
            List of result dicts for this batch.
        """
        encoding = tokenizer(
            cleaned_texts,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        ).to(self._device)

        with torch.no_grad():
            logits = model(**encoding).logits                    # (B, 3)
            probs  = torch.softmax(logits, dim=-1).cpu().numpy() # (B, 3)

        results = []
        for i, prob_row in enumerate(probs):
            pred_idx  = int(np.argmax(prob_row))
            label_key = f"LABEL_{pred_idx}"
            label, sentiment_weight = _LABEL_MAP[label_key]
            confidence = float(prob_row[pred_idx])

            # Continuous sentiment: weighted sum over all three classes
            continuous = float(
                prob_row[0] * -1.0 +   # negative
                prob_row[1] *  0.0 +   # neutral
                prob_row[2] *  1.0     # positive
            )

            results.append({
                "text":      raw_texts[i][:80],
                "label":     label,
                "score":     round(confidence, 4),
                "sentiment": round(continuous, 4),
            })

        return results

    def _fetch_reddit_posts(self, ticker: str, limit: int) -> list[str]:
        """
        Fetch recent Reddit post titles mentioning the ticker.

        Args:
            ticker: Ticker symbol used as search query.
            limit:  Maximum number of posts to retrieve.

        Returns:
            List of post title strings.
        """
        params = {
            "q": ticker,
            "sort": "new",
            "limit": limit,
            "type": "link",
        }
        resp = requests.get(
            REDDIT_SEARCH_URL,
            params=params,
            headers={"User-Agent": "zenith-iq/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        children = resp.json().get("data", {}).get("children", [])
        return [c["data"]["title"] for c in children if c.get("data", {}).get("title")]
