from datetime import datetime


def timestamp_now() -> str:
    return datetime.utcnow().isoformat()


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
