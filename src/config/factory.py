from api.binance.data_manager import BinanceDataManager
from app.executors.trade_executor import TradeExecutor
from api.openai.client import OpenAIClient
from api.coingecko.client import CoinGeckoClient
from app.analyzers.sentiment_analyzer import SentimentAnalyzer


def get_data_manager() -> BinanceDataManager:
    return BinanceDataManager()


def get_executor() -> TradeExecutor:
    return TradeExecutor()


def get_openai_client() -> OpenAIClient:
    return OpenAIClient()


def get_coin_gecko_client() -> CoinGeckoClient:
    return CoinGeckoClient()


def get_sentiment_analyzer() -> SentimentAnalyzer:
    return SentimentAnalyzer()
