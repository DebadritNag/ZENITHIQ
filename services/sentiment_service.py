from transformers import pipeline

_sentiment_pipeline = None


def get_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="ProsusAI/finbert",
        )
    return _sentiment_pipeline


def analyze_sentiment(text: str) -> dict:
    """Run FinBERT sentiment analysis on financial text."""
    pipe = get_pipeline()
    result = pipe(text[:512])  # FinBERT max token limit
    return result[0] if result else {}
