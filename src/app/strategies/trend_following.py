import pandas as pd
from typing import Dict
from app.strategies.base import StrategyPlugin
from config.settings import settings

class TrendFollowingStrategy(StrategyPlugin):
    """
    Compra/vende según cruces de medias móviles (SMA corto vs largo).
    """
    def __init__(self, data_manager, settings_obj):
        self.data_manager = data_manager
        self.settings = settings_obj
        self.interval = settings_obj.DEFAULT_CHECK_PRICE_INTERVAL
        # Periodos en horas o basado en settings
        self.short = settings_obj.OPTUNA_PARAM_SPACE.get('sma_period', (5,50))[0]  # default 5
        self.long = settings_obj.OPTUNA_PARAM_SPACE.get('sma_period', (5,50))[1]  # default 50

    def name(self) -> str:
        return "trend_following"

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
        df['sma_short'] = df['close'].rolling(self.short).mean()
        df['sma_long'] = df['close'].rolling(self.long).mean()
        if len(df) < self.long+1:
            return {"symbol": "BTCUSDC", "buy": False, "sell": False}
        prev_short = df['sma_short'].iloc[-2]
        prev_long = df['sma_long'].iloc[-2]
        curr_short = df['sma_short'].iloc[-1]
        curr_long = df['sma_long'].iloc[-1]
        signal = {"symbol": "BTCUSDC", "buy": False, "sell": False, "size": self.settings.INVESTMENT_AMOUNT}
        # Cruce al alza
        if prev_short <= prev_long and curr_short > curr_long:
            signal["buy"] = True
        # Cruce a la baja
        elif prev_short >= prev_long and curr_short < curr_long:
            signal["sell"] = True
        return signal
