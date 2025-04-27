from domain.ports import TradeDataProvider
from config.settings import Settings

class QuantityCalculator:
    """
    Calcula la cantidad a comprar basada en saldo disponible e inversión definida.
    """
    def __init__(self, data_provider: TradeDataProvider, settings: Settings):
        self.data_provider = data_provider
        self.investment_amount = settings.INVESTMENT_AMOUNT

    def calculate(self, symbol: str, balance_usdc: float) -> float:
        # No usar inversión fija; si no hay monto, nada que comprar
        if balance_usdc <= 0:
            return 0.0
        price = self.data_provider.get_price(symbol)
        if price is None or price <= 0:
            return 0.0
        # Calcular cantidad según monto USDC proporcionado
        return balance_usdc / price
