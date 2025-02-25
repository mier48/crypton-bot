import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple, Optional

from concurrent.futures import ThreadPoolExecutor, as_completed
from prettytable import PrettyTable

from api.binance.data_manager import BinanceDataManager
from api.openai.client import OpenAIClient
from api.coingecko.client import CoinGeckoClient
from app.analyzers.market_analyzer import MarketAnalyzer
from app.executors.trade_executor import TradeExecutor
from app.analyzers.sentiment_analyzer import SentimentAnalyzer
from utils.logger import setup_logger

from config.default import (
    DEFAULT_PROFIT_MARGIN,
    DEFAULT_SLEEP_INTERVAL,
    DEFAULT_INVESTMENT_AMOUNT,
    DEFAULT_MAX_BUY_PRICE,
    DEFAULT_STOP_LOSS_MARGIN,
    DEFAULT_CHECK_PRICE_INTERVAL,
    DEFAULT_HISTORICAL_RANGE_HOURS,
    INTERVAL_MAP,
    BUY_CATEGORIES
)

logging = setup_logger()

class BuyManager:
    """
    Gestor encargado de analizar y ejecutar compras de criptomonedas.
    """

    def __init__(
        self,
        data_manager: BinanceDataManager,
        executor: TradeExecutor,
        openai_client: OpenAIClient,
        sentiment_analyzer: SentimentAnalyzer,
        coin_gecko_client: CoinGeckoClient,
        profit_margin: float,
        stop_loss_margin: float,
        investment_amount: float,
        use_open_ai_api: bool,
        max_records: int = 500,
        max_workers: int = 10
    ):
        self.data_manager = data_manager
        self.executor = executor
        self.openai_client = openai_client
        self.sentiment_analyzer = sentiment_analyzer
        self.coin_gecko_client = coin_gecko_client
        self.profit_margin = profit_margin
        self.stop_loss_margin = stop_loss_margin
        self.investment_amount = investment_amount
        self.use_open_ai_api = use_open_ai_api
        self.max_records = max_records
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)

    def calculate_interval_in_milliseconds(self, interval: str) -> int:
        """
        Calcula la duración de un intervalo en milisegundos.

        :param interval: Intervalo de tiempo (e.g., "1m", "1h").
        :return: Duración en milisegundos.
        :raises ValueError: Si el intervalo no es soportado.
        """
        if interval not in INTERVAL_MAP:
            raise ValueError(f"Intervalo '{interval}' no soportado.")
        return INTERVAL_MAP[interval]

    def fetch_all_data(
        self, symbol: str, start_time: int, end_time: int, interval: str = DEFAULT_CHECK_PRICE_INTERVAL
    ) -> List[List[Any]]:
        """
        Recopila todos los datos históricos para un símbolo dentro de un rango de tiempo.

        :param symbol: Símbolo de la criptomoneda (e.g., "BTCUSDT").
        :param start_time: Tiempo de inicio en milisegundos.
        :param end_time: Tiempo de fin en milisegundos.
        :param interval: Intervalo de tiempo para los datos.
        :return: Lista de datos históricos.
        """
        all_data: List[List[Any]] = []
        interval_ms = self.calculate_interval_in_milliseconds(interval)
        max_time_range = interval_ms * self.max_records

        current_start = start_time
        while current_start < end_time:
            current_end = min(current_start + max_time_range, end_time)

            try:
                data = self.data_manager.fetch_historical_data(
                    symbol, current_start, current_end, interval=interval
                )
                if not data:
                    logging.debug(f"No se obtuvieron datos para {symbol} entre {current_start} y {current_end}.")
                    break

                all_data.extend(data)
                current_start = int(data[-1][6])

                if len(data) < self.max_records:
                    logging.debug(f"Datos insuficientes para continuar: {len(data)} registros obtenidos.")
                    break

                time.sleep(2)  # Respetar límites de la API
            except Exception as e:
                logging.error(f"Error al obtener datos para {symbol}: {e}")
                break

        return all_data

    def _process_coin(self, coin: Dict[str, Any], start_time: int, end_time: int) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Procesa un solo símbolo de moneda para analizar su tendencia.

        :param coin: Diccionario con información de la moneda.
        :param start_time: Tiempo de inicio para los datos históricos.
        :param end_time: Tiempo de fin para los datos históricos.
        :return: Tupla con el símbolo y los datos de análisis o None si falla.
        """
        symbol = coin.get('symbol')
        last_price = coin.get('lastPrice')
        logging.debug(f"Recopilando datos históricos de {symbol} (${last_price})...")
        try:
            data = self.fetch_all_data(symbol, start_time, end_time)
            logging.debug(f"Se han recopilado {len(data)} datos históricos para {symbol}.")

            if not data:
                return symbol, None

            analyzer = MarketAnalyzer(data, symbol)
            trend = analyzer.analyze()

            # Obtener indicadores técnicos
            sma_condition, rsi_condition, macd_condition, bb_condition, adx_condition, stochastic_condition = analyzer.get_signals()

            return symbol, {
                'trend': trend,
                'indicators': {
                    'sma': sma_condition,
                    'rsi': rsi_condition,
                    'macd': macd_condition,
                    'bb': bb_condition,
                    'adx': adx_condition,
                    'stochastic': stochastic_condition
                }
            }
        except Exception as e:
            logging.error(f"Error procesando {symbol}: {e}")
            return symbol, None

    def calculate_quantity_to_buy(self, symbol: str, usdt_balance: float) -> float:
        """
        Calcula la cantidad de criptomoneda a comprar basado en el saldo en USDT.

        :param symbol: Símbolo de la criptomoneda (e.g., "BTCUSDT").
        :param usdt_balance: Saldo disponible en USDT.
        :return: Cantidad a comprar.
        """
        if usdt_balance < self.investment_amount:
            return 0.0

        current_price = self.data_manager.get_price(symbol)
        if current_price <= 0:
            logging.warning(f"Precio actual inválido para {symbol}: {current_price}")
            return 0.0

        quantity = self.investment_amount / current_price
        return quantity

    def analyze_and_execute_buys(self) -> None:
        """
        Analiza el mercado para determinar si es un buen momento para comprar criptomonedas y ejecuta las compras.
        """
        categories = {}

        for category in BUY_CATEGORIES:
            try:
                logging.info(f"Obteniendo criptomonedas para la categoría: {category["name"]}")
                name = category["name"]
                method_name = category["method"]
                limit = category["limit"]
                min_price = category.get("min_price")
                max_price = category.get("max_price")

                # Obtener el método correspondiente del data_manager
                method = getattr(self.data_manager, method_name, None)
                if not method:
                    logging.error(f"Método '{method_name}' no encontrado en data_manager.")
                    continue

                # Obtener las criptomonedas según la categoría
                if "min_price" in category and "max_price" in category:
                    coins = method(min_price, max_price, limit)
                else:
                    coins = method(limit)
                categories[name] = coins
                logging.info(f"Categoría '{name}' obtenida con éxito.")
            except Exception as e:
                logging.error(f"Error al obtener criptomonedas para la categoría '{name}': {e}")

        now = datetime.now(timezone.utc)
        end_time = int(now.timestamp() * 1000)
        start_time = int((now - timedelta(hours=DEFAULT_HISTORICAL_RANGE_HOURS)).timestamp() * 1000)

        result: Dict[str, Dict[str, Any]] = {}

        # Preparar todas las monedas para procesar
        coins_to_process = [
            coin for coins in categories.values() for coin in coins
        ]

        # Enviar todas las tareas al ThreadPoolExecutor
        futures = {
            self.thread_pool.submit(self._process_coin, coin, start_time, end_time): coin.get('symbol')
            for coin in coins_to_process
        }

        for future in as_completed(futures):
            symbol, analysis = future.result()
            if analysis and analysis.get('trend'):
                result[symbol] = analysis

        logging.info(f"Mostrando {len(result)} recomendaciones de compra.")
        if not result:
            logging.info("No se encontraron recomendaciones de compra en este ciclo.")
            return

        # Obtener el saldo en USDT una sola vez
        usdt_balance = float(
            next(
                (item['free'] for item in self.data_manager.get_balance_summary() if item['asset'] == 'USDT'),
                0.0
            )
        )

        for symbol, data in result.items():
            try:
                if symbol == "USDCUSDT" or symbol == "USDTUSDT":
                    logging.info(f"No se puede comprar {symbol} directamente.")
                    continue
                
                current_price = self.data_manager.get_price(symbol)
                if current_price >= DEFAULT_MAX_BUY_PRICE:
                    logging.info(f"El precio de {symbol} es demasiado alto para comprar (${current_price:,.6f}).")
                    continue

                quantity_to_buy = self.calculate_quantity_to_buy(symbol, usdt_balance)
                if quantity_to_buy <= 0:
                    logging.info(f"Saldo insuficiente para comprar {symbol}.")
                    continue

                if self.use_open_ai_api:
                    # Obtener sentimiento y noticias relevantes
                    clean_symbol = symbol.replace("USDT", "")
                    sentiment = self.sentiment_analyzer.get_overall_sentiment(clean_symbol)
                    news_info = self.coin_gecko_client.fetch_crypto_news(clean_symbol)

                    indicators = data.get('indicators', {})
                    sma_condition = indicators.get('sma', "No disponible")
                    rsi_condition = indicators.get('rsi', "No disponible")
                    macd_condition = indicators.get('macd', "No disponible")
                    bb_condition = indicators.get('bb', "No disponible")
                    adx_condition = indicators.get('adx', "No disponible")
                    stochastic_condition = indicators.get('stochastic', "No disponible")

                    # Crear el prompt para OpenAI incluyendo los indicadores técnicos
                    prompt = (
                        "Eres un experto en trading y análisis de criptomonedas. Quieres tomar la mejor decisión para tu inversión.\n\n"
                        "### Contexto\n"
                        "Estás evaluando si es un buen momento para comprar una criptomoneda.\n\n"
                        "### Datos Actuales\n"
                        f"- Activo: {symbol}\n"
                        f"- Precio Actual: ${current_price:,.6f}\n"
                        f"- Cantidad a Comprar: {quantity_to_buy:,.6f}\n\n"
                        "### Indicadores Técnicos\n"
                        f"- Condición SMA (Media Móvil Simple): {sma_condition}\n"
                        f"- Condición RSI (Índice de Fuerza Relativa): {rsi_condition}\n"
                        f"- Condición MACD (Convergencia/Divergencia de la Media Móvil): {macd_condition}\n"
                        f"- Condición Bollinger Bands: {bb_condition}\n\n"
                        f"- Condición ADX: {adx_condition}\n"
                        f"- Condición Oscilador Estocástico: {stochastic_condition}\n\n"
                        "### Sentimiento del Mercado\n"
                        f"El sentimiento general para {clean_symbol} es {sentiment:.2f} (1 positivo, 0 neutro, -1 negativo).\n\n"
                        "### Noticias Relevantes\n"
                        f"{news_info}\n\n"
                        "### Pregunta\n"
                        "¿Recomiendas comprar ahora para aprovechar una posible subida o esperar una mejor oportunidad? "
                        "Responde solamente 'Comprar' o 'No comprar'.\n\n"
                        "Tu recomendación debe basarse en un análisis riguroso de los datos proporcionados y las condiciones del mercado."
                    )

                    # Consultar a OpenAI
                    response = self.openai_client.send_prompt(prompt)
                    logging.info(f"Respuesta de openAI para {symbol}: {response}")
                    if response and "comprar" in response.lower():
                        self._make_action(symbol, current_price, quantity_to_buy)
                    else:
                        logging.info(f"Decisión de no comprar la posición según recomendación de OpenAI para {symbol}.")
                else:
                    # Ejecutar la compra sin consultar a OpenAI
                    self._make_action(symbol, current_price, quantity_to_buy)

                # Opcional: espera entre cada operación para evitar sobrecargar la API
                time.sleep(5)

            except Exception as e:
                logging.error(f"Error al procesar la compra para {symbol}: {e}")

    def _make_action(self, symbol: str, current_price: float, quantity_to_buy: float) -> None:
        trade_result = self.executor.execute_trade(
            side="BUY",
            symbol=symbol,
            order_type="MARKET",
            positions=quantity_to_buy,
            price=current_price,
            reason="MANUAL_DECISION",
        )

        if trade_result:
            logging.info(f"Orden de compra ejecutada para {symbol}.")
        else: 
            logging.error(f"Error al procesar la compra para {symbol}")