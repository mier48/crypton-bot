import pandas as pd
from typing import Dict
from app.strategies.base import StrategyPlugin
from config.settings import settings

class ScalpingStrategy(StrategyPlugin):
    """
    Estrategia de scalping: compra en pequeñas caídas y vende en subidas rápidas.
    """
    def __init__(self, data_manager, settings_obj):
        self.data_manager = data_manager
        self.settings = settings_obj
        self.interval = settings_obj.DEFAULT_CHECK_PRICE_INTERVAL
        self.lookback = 2  # últimas 2 velas
        self.threshold = 0.001  # 0.1% de cambio

    def name(self) -> str:
        return "scalping"

    def analyze(self) -> Dict:
        klines = self.data_manager.fetch_historical_data(
            symbol="BTCUSDC",
            interval=self.interval,
            start_time=None,
            end_time=None
        )
        if not klines:
            return {"symbol": "BTCUSDC", "buy": False, "sell": False}
        df = pd.DataFrame(klines, columns=['open_time','open','high','low','close','volume',
                                           'close_time','quote_asset_volume','num_trades',
                                           'taker_buy_base','taker_buy_quote','ignore'])
        df['close'] = df['close'].astype(float)
        if len(df) < 2:
            return {"symbol": "BTCUSDC", "buy": False, "sell": False}
        prev, curr = df['close'].iloc[-2], df['close'].iloc[-1]
        change = (curr - prev) / prev
        signal = {"symbol": "BTCUSDC", "buy": False, "sell": False, "size": self.settings.INVESTMENT_AMOUNT}
        if change <= -self.threshold:
            signal["buy"] = True
        elif change >= self.threshold:
            signal["sell"] = True
        return signal
