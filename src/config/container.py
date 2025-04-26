from punq import Container

from config.settings import settings
from domain.ports import (
    NewsProvider, SocialMediaProvider, TrendsUseCase,
    TradeDataProvider, TradeExecutorPort, NotifierPort,
    BuyUseCase, SellUseCase
)
from api.news.newsapi.client import NewsAPIClient
from api.news.reddit.client import RedditClient
from api.binance.data_manager import BinanceDataManager
from app.managers.trends_manager import TrendsManager
from app.executors.trade_executor import TradeExecutor
from app.notifier import TelegramNotifier
from app.managers.buy_manager import BuyManager
from app.managers.sell_manager import SellManager
from app.services.asset_filter import AssetFilter
from app.services.quantity_calculator import QuantityCalculator
from app.services.buy_decision_engine import BuyDecisionEngine
from app.services.sell_decision_engine import SellDecisionEngine
from app.services.price_calculator import PriceCalculator

# Configurar contenedor de dependencias
container = Container()
# Registrar configuración de la aplicación
container.register_instance(settings)
# Registrar adaptadores de infraestructura (ports -> adapters)
container.register(NewsProvider, NewsAPIClient)
container.register(SocialMediaProvider, RedditClient)
container.register(TradeDataProvider, BinanceDataManager)
container.register(TradeExecutorPort, TradeExecutor)
container.register(NotifierPort, TelegramNotifier)
# Registrar casos de uso (interfaces -> implementaciones)
container.register(TrendsUseCase, TrendsManager)
container.register(BuyUseCase, BuyManager)
container.register(SellUseCase, SellManager)
container.register(AssetFilter, AssetFilter)
container.register(QuantityCalculator, QuantityCalculator)
container.register(BuyDecisionEngine, BuyDecisionEngine)
container.register(SellDecisionEngine, SellDecisionEngine)
container.register(PriceCalculator, PriceCalculator)


def get_container() -> Container:
    """
    Retorna el contenedor DI configurado.
    """
    return container
