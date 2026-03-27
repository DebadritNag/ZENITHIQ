from agents.base_agent import BaseAgent
from data_pipeline.stock_fetcher import fetch_stock_data


class StockAgent(BaseAgent):
    """Agent responsible for fetching and analyzing stock data."""

    def __init__(self):
        super().__init__("StockAgent")

    async def run(self, input_data: dict) -> dict:
        ticker = input_data.get("ticker")
        period = input_data.get("period", "1mo")
        data = fetch_stock_data(ticker, period)
        return {"ticker": ticker, "data": data}
