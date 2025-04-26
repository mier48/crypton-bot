from typing import Dict
from app.strategies.base import StrategyPlugin
from config.settings import settings
from api.openai.client import OpenAIClient
from api.coingecko.client import CoinGeckoClient

class ArbitrageStrategy(StrategyPlugin):
    """
    Detects price discrepancies between Binance and CoinGecko for simple spatial arbitrage.
    """
    def __init__(self, data_manager, settings_obj):
        self.data_manager = data_manager
        self.settings = settings_obj
        self.threshold = 0.005  # 0.5% price difference
        self.cg_client = CoinGeckoClient()

    def name(self) -> str:
        return "arbitrage"

    def analyze(self) -> Dict:
        symbol = "BTCUSDC"
        bin_price = self.data_manager.get_price(symbol)
        cg_data = self.cg_client.get_markets_data(vs_currency="usd", per_page=250)
        cg_price = None
        symbol_key = symbol[:-4].lower()
        if cg_data:
            for item in cg_data:
                if item.get('symbol') == symbol_key:
                    cg_price = item.get('current_price')
                    break
        if bin_price is None or cg_price is None:
            return {"symbol": symbol, "buy": False, "sell": False}
        signal = {"symbol": symbol, "buy": False, "sell": False, "size": self.settings.INVESTMENT_AMOUNT}
        # Buy on Binance if cheaper
        if bin_price < cg_price * (1 - self.threshold):
            signal["buy"] = True
        # Sell on Binance if more expensive
        elif bin_price > cg_price * (1 + self.threshold):
            signal["sell"] = True
        return signal
