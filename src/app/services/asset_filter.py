from typing import List
from domain.ports import TradeDataProvider
from config.settings import Settings

class AssetFilter:
    """
    Filtra activos según reglas definidas (no stablecoins, precio máximo).
    """
    def __init__(self, data_provider: TradeDataProvider, settings: Settings):
        self.data_provider = data_provider
        self.max_price = settings.MAX_BUY_PRICE

    def filter(self, symbols: List[str]) -> List[str]:
        valid = []
        for symbol in symbols:
            if symbol in ("USDCUSDC", "USDCUSDC"):
                continue
            price = self.data_provider.get_price(symbol)
            if price is None or price >= self.max_price:
                continue
            valid.append(symbol)
        return valid
