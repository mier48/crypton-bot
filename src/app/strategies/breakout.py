import pandas as pd
from typing import Dict
from app.strategies.base import StrategyPlugin
from config.settings import settings

class BreakoutStrategy(StrategyPlugin):
    """
    Compra cuando el precio rompe máximos de rango y vende cuando rompe mínimos.
    """
    def __init__(self, data_manager, settings_obj):
        self.data_manager = data_manager
        self.settings = settings_obj
        self.interval = settings_obj.DEFAULT_CHECK_PRICE_INTERVAL
        self.lookback = 20  # número de velas para definir el rango

    def name(self) -> str:
        return "breakout"

    def analyze(self) -> Dict:
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
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        # rango excluyendo la vela actual
        max_high = df['high'].iloc[-self.lookback-1:-1].max()
        min_low = df['low'].iloc[-self.lookback-1:-1].min()
        current = df['close'].iloc[-1]
        signal = {"symbol": "BTCUSDC", "buy": False, "sell": False, "size": self.settings.INVESTMENT_AMOUNT}
        if current > max_high:
            signal["buy"] = True
        elif current < min_low:
            signal["sell"] = True
        return signal
