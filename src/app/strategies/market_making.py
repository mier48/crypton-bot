import pandas as pd
from typing import Dict
from app.strategies.base import StrategyPlugin
from config.settings import settings

class MarketMakingStrategy(StrategyPlugin):
    """
    Coloca órdenes límite alrededor del precio medio para capturar el spread.
    """
    def __init__(self, data_manager, settings_obj):
        self.data_manager = data_manager
        self.settings = settings_obj
        self.interval = settings_obj.DEFAULT_CHECK_PRICE_INTERVAL
        self.lookback = 10  # velas para rango
        self.spread = 0.002  # 0.2% spread objetivo

    def name(self) -> str:
        return "market_making"

    def analyze(self) -> Dict:
        klines = self.data_manager.fetch_historical_data(
            symbol="BTCUSDC",
            interval=self.interval
        )
        if not klines:
            return {"symbol": "BTCUSDC", "buy": False, "sell": False}
        df = pd.DataFrame(klines, columns=['open_time','open','high','low','close','volume',
                                           'close_time','quote_asset_volume','num_trades',
                                           'taker_buy_base','taker_buy_quote','ignore'])
        df['close'] = df['close'].astype(float)
        window = df['close'].iloc[-self.lookback:]
        mid = (window.max() + window.min()) / 2
        current = window.iloc[-1]
        signal = {"symbol": "BTCUSDC", "buy": False, "sell": False, "size": self.settings.INVESTMENT_AMOUNT, "order_type": "LIMIT"}
        if current < mid * (1 - self.spread):
            signal["buy"] = True
        elif current > mid * (1 + self.spread):
            signal["sell"] = True
        return signal
