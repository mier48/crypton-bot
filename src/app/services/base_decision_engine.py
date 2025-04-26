from typing import Tuple, Optional
from api.openai.client import OpenAIClient
from app.analyzers.sentiment_analyzer import SentimentAnalyzer
from api.coingecko.client import CoinGeckoClient
from config.settings import settings


class BaseDecisionEngine:
    """
    Base decision engine providing common utilities for buy/sell logic.
    """
    openai_client: OpenAIClient
    sentiment_analyzer: SentimentAnalyzer
    coin_gecko_client: CoinGeckoClient
    use_open_ai: bool

    def __init__(
        self,
        openai_client: OpenAIClient,
        sentiment_analyzer: SentimentAnalyzer,
        coin_gecko_client: CoinGeckoClient,
    ) -> None:
        """
        Initializes the base decision engine.

        Args:
            openai_client (OpenAIClient): Client for OpenAI API.
            sentiment_analyzer (SentimentAnalyzer): Analyzer for market sentiment.
            coin_gecko_client (CoinGeckoClient): Client for crypto news.
        """
        self.openai_client = openai_client
        self.sentiment_analyzer = sentiment_analyzer
        self.coin_gecko_client = coin_gecko_client
        self.use_open_ai = settings.USE_OPEN_AI_API

    def get_sentiment_and_news(self, symbol: str) -> Tuple[float, str]:
        """
        Fetches overall sentiment and latest news for a given asset.

        Args:
            symbol (str): Asset symbol, e.g. 'BTCUSDC'.

        Returns:
            Tuple[float, str]: Sentiment score and news info string.
        """
        clean_symbol = symbol.replace("USDC", "")
        sentiment: float = self.sentiment_analyzer.get_overall_sentiment(clean_symbol)
        news_info: str = self.coin_gecko_client.fetch_crypto_news(clean_symbol)
        return sentiment, news_info

    def send_openai_prompt(self, prompt: str) -> Optional[str]:
        """
        Sends a prompt to OpenAI and returns the response.

        Args:
            prompt (str): Prompt text.

        Returns:
            Optional[str]: OpenAI response or None.
        """
        return self.openai_client.send_prompt(prompt)
