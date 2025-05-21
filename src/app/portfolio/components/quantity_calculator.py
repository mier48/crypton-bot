from typing import Optional
from src.config.settings import settings
from src.app.portfolio.adapters import BinanceDataProviderAdapter
from src.utils.logger import setup_logger

logger = setup_logger()

class QuantityCalculator:
    """
    Calcula las cantidades para operaciones de compra y venta en rebalanceo de portafolio.
    Versión especializada para el módulo de portafolio.
    """
    
    def __init__(self, data_provider: BinanceDataProviderAdapter = None):
        """
        Inicializa el calculador de cantidades.
        
        Args:
            data_provider: Proveedor de datos de trading (opcional)
        """
        self.data_provider = data_provider
    
    def calculate_buy_quantity(self, symbol: str, price: float, usdc_amount: float) -> float:
        """
        Calcula la cantidad a comprar basada en un valor en USDC.
        
        Args:
            symbol: Símbolo sin el sufijo USDC (ej: 'BTC')
            price: Precio actual del activo
            usdc_amount: Cantidad en USDC a invertir
            
        Returns:
            float: Cantidad a comprar
        """
        if price <= 0:
            return 0.0
            
        # Calcular cantidad base
        quantity = usdc_amount / price
        
        # Redondear según reglas de Binance (esto podría mejorarse para cada activo)
        if price >= 1000:  # BTC y similares
            quantity = round(quantity, 5)  # 5 decimales
        elif price >= 100:  # ETH y similares
            quantity = round(quantity, 4)  # 4 decimales
        elif price >= 1:  # Activos de precio medio
            quantity = round(quantity, 3)  # 3 decimales
        elif price >= 0.1:  # Activos de precio bajo
            quantity = round(quantity, 2)  # 2 decimales
        elif price >= 0.01:  # Activos de precio muy bajo
            quantity = round(quantity, 1)  # 1 decimal
        else:  # Precio extremadamente bajo
            quantity = int(quantity)  # Sin decimales
        
        return quantity
    
    def calculate_sell_quantity(self, symbol: str, price: float, usdc_amount: float) -> float:
        """
        Calcula la cantidad a vender basada en un valor en USDC.
        
        Args:
            symbol: Símbolo sin el sufijo USDC (ej: 'BTC')
            price: Precio actual del activo
            usdc_amount: Valor en USDC a vender
            
        Returns:
            float: Cantidad a vender
        """
        # Para venta, aplicamos la misma lógica que para compra
        # pero verificando no exceder balance disponible
        quantity = self.calculate_buy_quantity(symbol, price, usdc_amount)
        
        # Si tenemos data_provider, verificar balance disponible
        if self.data_provider:
            try:
                balances = self.data_provider.get_balance_summary()
                if balances:
                    # Buscar el activo en los balances
                    for balance in balances:
                        if balance.get('asset', '') == symbol:
                            available = float(balance.get('free', 0))
                            # Asegurar no vender más de lo disponible
                            quantity = min(quantity, available)
                            break
            except Exception as e:
                logger.warning(f"Error verificando balance para {symbol}: {e}")
        
        return quantity
