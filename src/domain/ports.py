from typing import Protocol, List, Dict, Any, Optional

class NewsProvider(Protocol):
    """
    Puerto para obtener artículos de noticias.
    """
    def fetch_articles(self, keyword: str, limit: int) -> List[Dict[str, Any]]:
        ...

class SocialMediaProvider(Protocol):
    """
    Puerto para obtener publicaciones de redes sociales.
    """
    def fetch_posts(self, keyword: str, limit: int) -> List[Dict[str, Any]]:
        ...

class TrendsUseCase(Protocol):
    """
    Caso de uso para recuperar tendencias combinadas.
    """
    def fetch_trends(self, keyword: str, limit: int) -> List[Dict[str, Any]]:
        ...

class TradeDataProvider(Protocol):
    """
    Puerto para operaciones de datos de trading.
    """
    def get_price(self, symbol: str) -> Optional[float]: ...
    def get_balance_summary(self) -> List[Dict[str, Any]]: ...
    def get_all_orders(self, symbol: str) -> Optional[List[Dict[str, Any]]]: ...
    def create_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None
    ) -> Optional[Dict[str, Any]]: ...

class TradeExecutorPort(Protocol):
    """
    Puerto para ejecutar órdenes de compra/venta.
    """
    def execute_trade(
        self,
        side: str,
        symbol: str,
        order_type: str,
        positions: float,
        reason: Optional[str] = None,
        price: Optional[float] = None,
        percentage_gain: Optional[float] = None
    ) -> Optional[bool]: ...

class NotifierPort(Protocol):
    """
    Puerto para notificaciones de trading (Telegram, email, etc.).
    """
    def notify_trade(
        self,
        side: str,
        symbol: str,
        quantity: float,
        price: float,
        balance: float,
        percentage_gain: Optional[float] = None,
        reason: Optional[str] = None
    ) -> None: ...

class BuyUseCase(Protocol):
    """
    Caso de uso para ejecución de compras.
    """
    def execute_buys(self) -> None: ...

class SellUseCase(Protocol):
    """
    Caso de uso para ejecución de ventas.
    """
    def execute_sells(self) -> None: ...
