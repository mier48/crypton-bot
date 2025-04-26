from typing import Dict, Any
from api.openai.client import OpenAIClient
from app.analyzers.sentiment_analyzer import SentimentAnalyzer
from api.coingecko.client import CoinGeckoClient
from domain.ports import TradeDataProvider
from config.settings import settings
import logging
from app.services.base_decision_engine import BaseDecisionEngine

logger = logging.getLogger(__name__)

class BuyDecisionEngine(BaseDecisionEngine):
    """
    Motor de decisión para compras usando OpenAI o reglas internas.
    """
    def __init__(
        self,
        openai_client: OpenAIClient,
        sentiment_analyzer: SentimentAnalyzer,
        coin_gecko_client: CoinGeckoClient,
        data_provider: TradeDataProvider
    ) -> None:
        super().__init__(openai_client, sentiment_analyzer, coin_gecko_client)
        self.data_provider = data_provider

    def should_buy(
        self,
        symbol: str,
        current_price: float,
        quantity: float,
        indicators: Dict[str, Any]
    ) -> bool:
        """
        Devuelve True si comprar, basado en reglas o OpenAI.
        """
        # Reglas básicas sin OpenAI
        if not self.use_open_ai:
            return True

        # Datos de sentimiento y noticias
        sentiment, news_info = self.get_sentiment_and_news(symbol)

        # Indicadores técnicos
        sma = indicators.get('sma', 'N/A')
        rsi = indicators.get('rsi', 'N/A')
        macd = indicators.get('macd', 'N/A')
        bb = indicators.get('bb', 'N/A')

        prompt = (
            f"Eres un experto en trading. Analiza si comprar el activo {symbol} al precio ${current_price:.6f}, cantidad {quantity:.6f}.\n\n"
            f"Sentimiento: {sentiment:.2f}. Noticias: {news_info}\n\n"
            f"Indicadores: SMA={sma}, RSI={rsi}, MACD={macd}, BB={bb}.\n"
            "Responde solo 'Comprar' o 'No comprar'."
        )
        response = self.send_openai_prompt(prompt)
        return bool(response and 'comprar' in response.lower())
