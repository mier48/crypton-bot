from typing import Tuple, List, Dict
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.logger import setup_logger
from api.binance.data_manager import BinanceDataManager
from api.openai.client import OpenAIClient
from api.coingecko.client import CoinGeckoClient
from app.analyzers.sentiment_analyzer import SentimentAnalyzer

logger = setup_logger()

class PreTradeAnalyzer:
    """
    Analizador que evalúa las condiciones del mercado y el sentimiento antes de realizar operaciones.
    """

    # Definición de constantes a nivel de clase para facilitar la configuración y mantenimiento
    VOLATILITY_THRESHOLD = 0.7
    VOLUME_THRESHOLD = 1e9  # 1 mil millones de USD
    BTC_DOMINANCE_THRESHOLD = 30.0  # porcentaje
    ETH_DOMINANCE_THRESHOLD = 20.0  # porcentaje
    SENTIMENT_KEYWORDS = [
        "cryptocurrency", "btc", "ethereum", "altcoins", "defi", "nft",
        "market sentiment", "bull run", "bear market", "bitcoin halving",
        "crypto fear and greed", "inflation", "recession", "regulation"
    ]
    SYMBOLS = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "ADAUSDT", "SOLUSDT"]
    SENTIMENT_ANALYSIS_COUNT = 10

    def __init__(self):
        self.binance_data_manager = BinanceDataManager()
        self.open_ai_client = OpenAIClient()
        self.coingecko_client = CoinGeckoClient()
        self.sentiment_analyzer = SentimentAnalyzer()

    def _fetch_overall_sentiment(self, keywords: List[str]) -> Tuple[float, str]:
        """
        Calcula el sentimiento general basado en múltiples palabras clave.

        :param keywords: Lista de palabras clave para analizar.
        :return: Promedio del sentimiento y detalle del sentimiento individual.
        """
        sentiments: Dict[str, float] = {}
        try:
            # Utiliza ThreadPoolExecutor para paralelizar las llamadas de análisis de sentimiento
            with ThreadPoolExecutor() as executor:
                future_to_keyword = {
                    executor.submit(self.sentiment_analyzer.get_overall_sentiment, keyword, self.SENTIMENT_ANALYSIS_COUNT): keyword
                    for keyword in keywords
                }
                for future in as_completed(future_to_keyword):
                    keyword = future_to_keyword[future]
                    try:
                        sentiment = future.result()
                        sentiments[keyword] = sentiment
                    except Exception as e:
                        logger.error(f"Error al obtener el sentimiento para '{keyword}': {e}")
                        sentiments[keyword] = 0.0  # Asigna un sentimiento neutral en caso de error

            if sentiments:
                average_sentiment = sum(sentiments.values()) / len(sentiments)
                logger.info(f"Puntuaciones de sentimiento: {sentiments}")
                return average_sentiment, f"Puntuaciones individuales de sentimiento: {sentiments}"
            else:
                logger.warning("No se obtuvieron puntuaciones de sentimiento.")
                return 0.0, "No hay datos de sentimiento disponibles."
        except Exception as e:
            logger.error(f"Error al calcular el sentimiento: {e}")
            return -1.0, "Error en el análisis de sentimiento."

    def _fetch_volatilities(self, symbols: List[str]) -> List[float]:
        """
        Obtiene la volatilidad del mercado para una lista de símbolos.

        :param symbols: Lista de símbolos de trading.
        :return: Lista de valores de volatilidad.
        """
        volatilities = []
        with ThreadPoolExecutor() as executor:
            future_to_symbol = {
                executor.submit(self.binance_data_manager.get_market_volatility, symbol): symbol
                for symbol in symbols
            }
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    volatility = future.result()
                    if volatility is not None:
                        volatilities.append(volatility)
                        logger.debug(f"Volatilidad para {symbol}: {volatility}")
                    else:
                        logger.warning(f"No se obtuvo la volatilidad para {symbol}.")
                except Exception as e:
                    logger.error(f"Error al obtener la volatilidad para {symbol}: {e}")
        return volatilities

    def _analyze_market_conditions(
        self, global_data: Dict, mean_volatility: float, average_sentiment: float
    ) -> Tuple[bool, str]:
        """
        Evalúa las condiciones del mercado usando datos globales, volatilidad y sentimiento.

        :param global_data: Datos globales del mercado.
        :param mean_volatility: Volatilidad media calculada del mercado.
        :param average_sentiment: Sentimiento promedio del mercado.
        :return: Tupla indicando si se debe operar y el motivo.
        """
        total_market_cap = global_data.get('total_market_cap', {}).get('usd', 0.0)
        total_volume = global_data.get('total_volume', {}).get('usd', 0.0)
        market_cap_percentage = global_data.get('market_cap_percentage', {})

        btc_dominance = market_cap_percentage.get('btc', 0.0)
        eth_dominance = market_cap_percentage.get('eth', 0.0)

        logger.info(
            f"Datos Globales - Capitalización Total del Mercado: {total_market_cap}, Volumen Total: {total_volume}, "
            f"Dominancia - BTC: {btc_dominance}%, ETH: {eth_dominance}%"
        )

        # Verifica la volatilidad
        if mean_volatility > self.VOLATILITY_THRESHOLD:
            return False, f"Alta volatilidad detectada: {mean_volatility:.2f}"

        # Verifica el volumen del mercado
        if total_volume < self.VOLUME_THRESHOLD:
            return False, f"Volumen de mercado bajo: {total_volume} USD"

        # Verifica la dominancia de BTC y ETH
        if btc_dominance < self.BTC_DOMINANCE_THRESHOLD or eth_dominance < self.ETH_DOMINANCE_THRESHOLD:
            return False, (
                f"Baja dominancia de BTC ({btc_dominance}%) o ETH ({eth_dominance}%)."
            )

        # Verifica el sentimiento promedio
        if average_sentiment < 0:
            return False, f"Sentimiento general negativo detectado: {average_sentiment:.2f}."

        return True, "Las condiciones del mercado son favorables."

    def should_trade(self) -> Tuple[bool, str]:
        """
        Evalúa si es un buen momento para operar.

        :return: Tupla donde el primer elemento indica si se debe operar y el segundo es el motivo.
        """
        try:
            # Obtener el sentimiento general
            average_sentiment, sentiment_details = self._fetch_overall_sentiment(self.SENTIMENT_KEYWORDS)
            logger.info(sentiment_details)

            # Obtener las volatilidades
            volatilities = self._fetch_volatilities(self.SYMBOLS)

            if volatilities:
                mean_volatility = sum(volatilities) / len(volatilities)
                logger.info(f"Volatilidad media del mercado: {mean_volatility:.2f}")
            else:
                logger.warning("No se pudieron obtener datos de volatilidad del mercado.")
                mean_volatility = float('inf')  # Asigna alta volatilidad para prevenir operaciones

            # Obtener datos globales desde CoinGecko
            global_data = self.coingecko_client.get_global_data()
            if not global_data:
                return False, "No se pudieron obtener datos globales de CoinGecko."

            # Analizar condiciones de mercado
            should_trade, reason = self._analyze_market_conditions(
                global_data, mean_volatility, average_sentiment
            )

            if should_trade:
                logger.info("MarketAnalyzer: Las condiciones del mercado son favorables.")
            else:
                logger.info(f"MarketAnalyzer: {reason}")

            return should_trade, reason
        except Exception as e:
            logger.error(f"Error inesperado durante el análisis de condiciones del mercado: {e}")
            return False, "Error inesperado al analizar el mercado."
