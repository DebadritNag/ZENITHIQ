from agents.base_agent import BaseAgent
from services.gemini_service import query_gemini


class GeminiAgent(BaseAgent):
    """Agent that uses Gemini API for financial reasoning and summaries."""

    def __init__(self):
        super().__init__("GeminiAgent")

    async def run(self, input_data: dict) -> dict:
        prompt = input_data.get("prompt", "")
        response = await query_gemini(prompt)
        return {"response": response}
