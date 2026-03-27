"""
Gemini Service
--------------
Async client using the google-genai SDK (replaces deprecated google-generativeai).
All prompt construction and response parsing lives in gemini_reasoning.py.
"""

from __future__ import annotations

import logging
from google import genai
from google.genai import types

from config import settings

logger = logging.getLogger(__name__)

if not settings.gemini_api_key:
    logger.warning("GEMINI_API_KEY is not set — Gemini calls will fail at runtime.")

# One client per process
_client = genai.Client(api_key=settings.gemini_api_key)

# Best free-tier model with generateContent support
MODEL = "gemini-2.0-flash"


async def query_gemini(
    prompt: str,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
) -> str:
    """
    Send a plain-text prompt to Gemini and return the response string.

    Args:
        prompt:            Full prompt string.
        temperature:       Sampling temperature (0.0–1.0).
        max_output_tokens: Hard cap on response length.

    Returns:
        Stripped response text from Gemini.

    Raises:
        RuntimeError: If Gemini returns an empty or blocked response.
    """
    response = _client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        ),
    )

    text = response.text
    if not text:
        raise RuntimeError("Gemini returned an empty response. Prompt may have been blocked.")

    return text.strip()


def gemini_available() -> bool:
    """Quick check — returns False if the API key is missing."""
    return bool(settings.gemini_api_key)
