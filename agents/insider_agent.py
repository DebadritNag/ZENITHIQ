"""
Insider Agent
-------------
Scrapes OpenInsider for recent insider buy/sell transactions
and derives a directional signal score.

Falls back to get_mock_insider_activity() when scraping fails
(network unavailable, ticker not on OpenInsider, etc.).
"""

import requests
from bs4 import BeautifulSoup
from typing import Any

from agents.base_agent import BaseAgent, AgentResult
from data_pipeline.mock_data import get_mock_insider_activity


OPENINSIDER_URL = (
    "http://openinsider.com/screener?s={ticker}&o=&pl=&ph=&ll=&lh="
    "&fd=730&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1"
    "&vl=&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999"
    "&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h="
    "&oc2l=&oc2h=&sortcol=0&cnt=40&action=1"
)


class InsiderAgent(BaseAgent):
    """
    Parses insider trading activity from OpenInsider.

    Workflow:
        1. Scrape the OpenInsider screener table for the ticker.
        2. Parse each transaction row (date, insider, type, shares, value).
        3. Compute buy/sell ratio and derive a 0–1 signal score.
    """

    def __init__(self):
        super().__init__("InsiderAgent")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(self, ticker: str, **kwargs: Any) -> AgentResult:
        """
        Analyse insider trading activity for `ticker`.

        Attempts live OpenInsider scrape first; falls back to
        get_mock_insider_activity() on any failure or empty result.

        Args:
            ticker:   Stock ticker symbol.
            use_mock: Force mock data (default False — tries live first).

        Returns:
            AgentResult with transaction list and 0–1 insider signal score.
            Score > 0.5 indicates net buying; < 0.5 indicates net selling.
        """
        use_mock = kwargs.get("use_mock", False)

        try:
            transactions = []
            if not use_mock:
                try:
                    transactions = self._scrape_transactions(ticker)
                except Exception as scrape_exc:
                    self.logger.warning(
                        f"[InsiderAgent] OpenInsider scrape failed for {ticker}: {scrape_exc} "
                        f"— falling back to mock data"
                    )

            if not transactions:
                return self._mock_result(ticker)

            summary = self._summarise(transactions)
            score   = self._score(summary)

            return AgentResult(
                self.name,
                {
                    "transaction_count":   len(transactions),
                    "recent_transactions": transactions[:5],
                    "summary":             summary,
                    "source":              "openinsider",
                },
                score=score,
            )

        except Exception as exc:
            self.logger.error(f"InsiderAgent failed for {ticker}: {exc}")
            return AgentResult(self.name, {}, score=0.5, error=str(exc))

    def _mock_result(self, ticker: str) -> AgentResult:
        """
        Build an AgentResult from simulated insider activity.

        Args:
            ticker: Stock ticker symbol.

        Returns:
            AgentResult with mock insider data and derived score.
        """
        mock = get_mock_insider_activity(ticker)
        intensity = mock["intensity"]   # -1 to +1

        # Map intensity [-1, +1] → score [0, 1]
        score = round((intensity + 1.0) / 2.0, 4)

        self.logger.info(
            f"[InsiderAgent] Mock data for {ticker}: "
            f"activity={mock['activity']} intensity={intensity}"
        )

        return AgentResult(
            self.name,
            {
                "transaction_count":   0,
                "recent_transactions": [],
                "summary": {
                    "buy_count":   1 if mock["activity"] == "buy"  else 0,
                    "sell_count":  1 if mock["activity"] == "sell" else 0,
                    "buy_value":   abs(intensity) * 1_000_000 if mock["activity"] == "buy"  else 0.0,
                    "sell_value":  abs(intensity) * 1_000_000 if mock["activity"] == "sell" else 0.0,
                },
                "mock_activity":  mock["activity"],
                "mock_intensity": intensity,
                "source":         "mock",
            },
            score=score,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _scrape_transactions(self, ticker: str) -> list[dict]:
        """
        Scrape and parse the OpenInsider results table.

        Args:
            ticker: Ticker symbol.

        Returns:
            List of transaction dicts with keys:
            filing_date, trade_date, insider_name, title,
            trade_type, price, qty, owned, value.
        """
        url = OPENINSIDER_URL.format(ticker=ticker.upper())
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"class": "tinytable"})
        if not table:
            return []

        rows = table.find_all("tr")[1:]  # skip header
        transactions = []
        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 13:
                continue
            transactions.append({
                "filing_date": cols[1],
                "trade_date": cols[2],
                "ticker": cols[3],
                "insider_name": cols[4],
                "title": cols[5],
                "trade_type": cols[6],   # 'P - Purchase' or 'S - Sale'
                "price": cols[7],
                "qty": cols[8],
                "owned": cols[9],
                "value": cols[11],
            })
        return transactions

    def _summarise(self, transactions: list[dict]) -> dict:
        """
        Aggregate buy vs sell counts and total values.

        Args:
            transactions: Parsed transaction list.

        Returns:
            Dict with buy_count, sell_count, buy_value, sell_value.
        """
        buy_count = sell_count = 0
        buy_value = sell_value = 0.0

        for t in transactions:
            trade_type = t.get("trade_type", "").upper()
            raw_value = t.get("value", "0").replace("$", "").replace(",", "").replace("+", "")
            try:
                value = float(raw_value)
            except ValueError:
                value = 0.0

            if "P" in trade_type:
                buy_count += 1
                buy_value += value
            elif "S" in trade_type:
                sell_count += 1
                sell_value += value

        return {
            "buy_count": buy_count,
            "sell_count": sell_count,
            "buy_value": round(buy_value, 2),
            "sell_value": round(sell_value, 2),
        }

    def _score(self, summary: dict) -> float:
        """
        Derive a 0–1 insider signal from buy/sell ratio.

        Score = buy_value / (buy_value + sell_value)
        Falls back to count ratio if values are zero.

        Args:
            summary: Output of _summarise().

        Returns:
            Float between 0.0 (heavy selling) and 1.0 (heavy buying).
        """
        bv = summary["buy_value"]
        sv = summary["sell_value"]
        bc = summary["buy_count"]
        sc = summary["sell_count"]

        if bv + sv > 0:
            return round(bv / (bv + sv), 4)
        if bc + sc > 0:
            return round(bc / (bc + sc), 4)
        return 0.5
