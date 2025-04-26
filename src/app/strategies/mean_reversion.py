import pandas as pd
from typing import Dict
from app.strategies.base import StrategyPlugin
from config.settings import settings

class MeanReversionStrategy(StrategyPlugin):
    """
    Compra cuando el precio cae por debajo de la media histórica y vende cuando supera la media.
    """
    def __init__(self, data_manager, settings_obj):
        self.data_manager = data_manager
        self.settings = settings_obj
        self.interval = settings_obj.DEFAULT_CHECK_PRICE_INTERVAL
        self.lookback = settings_obj.DEFAULT_HISTORICAL_RANGE_HOURS
        self.threshold = 0.01  # 1% de desviación

    def name(self) -> str:
        return "mean_reversion"

    def analyze(self) -> Dict:
        # Obtener datos históricos
        klines = self.data_manager.fetch_historical_data(
            symbol="BTCUSDC",
            interval=self.interval,
            start_time=None,
            end_time=None
        )
        if not klines:
            return {"symbol": "BTCUSDC", "buy": False, "sell": False}
        df = pd.DataFrame(klines, columns=[
            'open_time','open','high','low','close','volume',
            'close_time','quote_asset_volume','num_trades',
            'taker_buy_base','taker_buy_quote','ignore'
        ])
        df['close'] = df['close'].astype(float)

        mean_price = df['close'].mean()
        current_price = df['close'].iloc[-1]

        signal = {"symbol": "BTCUSDC", "buy": False, "sell": False, "size": self.settings.INVESTMENT_AMOUNT}
        if current_price < mean_price * (1 - self.threshold):
            signal["buy"] = True
        elif current_price > mean_price * (1 + self.threshold):
            signal["sell"] = True
        return signal
