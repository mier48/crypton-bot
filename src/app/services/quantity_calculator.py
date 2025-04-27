from domain.ports import TradeDataProvider
from config.settings import Settings

class QuantityCalculator:
    """
    Calcula la cantidad a comprar basada en saldo disponible e inversión definida.
    """
    def __init__(self, data_provider: TradeDataProvider, settings: Settings):
        self.data_provider = data_provider
        self.investment_amount = settings.INVESTMENT_AMOUNT

    def calculate(self, symbol: str) -> float:
        """
        Retorna el monto fijo de inversión a gastar como quoteOrderQty en compra MARKET.
        """
        return max(0.0, self.investment_amount)
