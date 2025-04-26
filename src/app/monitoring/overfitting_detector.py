import pandas as pd

class OverfittingDetector:
    """
    Detect overfitting by comparing train and test backtest performance.
    """
    def __init__(self, threshold: float = 0.1):
        # threshold difference between train and test mean returns to flag overfitting
        self.threshold = threshold

    def is_overfitting(self, train_returns: pd.Series, test_returns: pd.Series) -> bool:
        """
        Returns True if the difference between train and test mean returns exceeds threshold.
        :param train_returns: Series of train period returns.
        :param test_returns: Series of test period returns.
        """
        train_perf = train_returns.mean()
        test_perf = test_returns.mean()
        gap = train_perf - test_perf
        return gap > self.threshold
