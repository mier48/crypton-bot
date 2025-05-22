from domain.ports import TradeDataProvider
from config.settings import Settings
from loguru import logger

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
        Limitado por el balance disponible de USDC.
        """
        # Obtener el balance disponible de USDC
        balances = self.data_provider.get_balance_summary()
        usdc_balance = next((float(b['free']) for b in balances if b['asset'] == 'USDC'), 0.0)
        
        # Limitar la inversión al balance disponible
        investment = min(usdc_balance, self.investment_amount)
        
        if investment < self.investment_amount:
            logger.info(f"Inversión ajustada de {self.investment_amount:.2f} a {investment:.2f} USDC por balance insuficiente")
            
        return max(0.0, investment)
