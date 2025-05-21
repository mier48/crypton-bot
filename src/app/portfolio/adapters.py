from typing import Dict, List, Optional, Any
from src.api.binance.data_manager import BinanceDataManager
from domain.ports import TradeDataProvider
from loguru import logger

class BinanceDataProviderAdapter(TradeDataProvider):
    """
    Adaptador que conecta BinanceDataManager con la interfaz TradeDataProvider.
    Esto asegura compatibilidad con componentes que esperan esta interfaz.
    """
    
    def __init__(self, data_manager: BinanceDataManager):
        """
        Inicializa el adaptador con un gestor de datos existente.
        
        Args:
            data_manager: Instancia de BinanceDataManager
        """
        self.data_manager = data_manager
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        Obtiene el precio actual de un par de mercado.
        """
        return self.data_manager.get_price(symbol)
    
    def get_balance_summary(self) -> List[Dict[str, Any]]:
        """
        Obtiene el resumen de balances de la cuenta.
        """
        return self.data_manager.get_balance_summary()
    
    def get_all_orders(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene todas las u00f3rdenes para un su00edmbolo dado.
        """
        return self.data_manager.get_all_orders(symbol)
    
    def create_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Crea una orden en la exchange.
        """
        return self.data_manager.create_order(
            symbol=symbol,
            side=side,
            type_=type_,
            quantity=quantity,
            price=price
        )
