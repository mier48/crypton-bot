import backtrader as bt
import pandas as pd
from datetime import datetime
from api.binance.data_manager import BinanceDataManager
from app.analyzers.market_analyzer import MarketAnalyzer
from app.services.sell_decision_engine import SellDecisionEngine
from app.services.buy_decision_engine import BuyDecisionEngine
from config.settings import settings

class CryptoStrategy(bt.Strategy):
    """
    Estrategia de ejemplo que usa MarketAnalyzer y decision engines para backtesting.
    """
    params = dict(
        symbol='BTCUSDC',
        from_date=datetime(2025, 1, 1),
        to_date=datetime(2025, 4, 1),
        interval='1h'
    )

    def __init__(self):
        # Inicializar componentes
        self.data_manager = BinanceDataManager()
        self.market_analyzer = MarketAnalyzer(settings)
        self.buy_engine = BuyDecisionEngine(None, None, None, self.data_manager)
        self.sell_engine = SellDecisionEngine(None, None, None, None)

    def next(self):
        price = self.data.close[0]
        dt = self.data.datetime.datetime(0)
        # Señal de compra y venta usando MarketAnalyzer
        if self.market_analyzer.is_buy_signal(self.datas[0]):
            self.buy(size=1)
        elif self.market_analyzer.is_sell_signal(self.datas[0]):
            self.sell(size=1)
