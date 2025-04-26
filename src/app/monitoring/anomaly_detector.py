import pandas as pd
from sklearn.ensemble import IsolationForest

class AnomalyDetector:
    """
    Detect anomalies in bot behavior using IsolationForest.
    """
    def __init__(self, contamination: float = 0.01, random_state: int = 42):
        self.model = IsolationForest(contamination=contamination, random_state=random_state)

    def fit(self, X: pd.DataFrame):
        """
        Fit the anomaly detection model.
        :param X: DataFrame of features.
        """
        self.model.fit(X)

    def detect(self, X: pd.DataFrame) -> pd.Series:
        """
        Predict anomalies on dataset.
        :param X: DataFrame of features.
        :return: Series of booleans, True if anomaly.
        """
        preds = self.model.predict(X)
        # -1 indicates anomaly
        return pd.Series(preds == -1, index=X.index)
