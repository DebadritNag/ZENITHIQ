import numpy as np
from sklearn.linear_model import LinearRegression


class StockPricePredictor:
    """Simple linear regression model for stock price trend prediction."""

    def __init__(self):
        self.model = LinearRegression()

    def train(self, prices: list[float]):
        X = np.arange(len(prices)).reshape(-1, 1)
        y = np.array(prices)
        self.model.fit(X, y)

    def predict(self, steps: int = 5) -> list[float]:
        last_idx = self.model.n_features_in_
        future_X = np.arange(last_idx, last_idx + steps).reshape(-1, 1)
        return self.model.predict(future_X).tolist()
