import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple, Optional, Set

from concurrent.futures import ThreadPoolExecutor, as_completed
from prettytable import PrettyTable

from domain.ports import TradeDataProvider, TradeExecutorPort, BuyUseCase
from app.analyzers.market_analyzer import MarketAnalyzer
from utils.logger import setup_logger
from app.services.asset_filter import AssetFilter
from app.services.quantity_calculator import QuantityCalculator
from app.services.buy_decision_engine import BuyDecisionEngine
from app.services.investment_calculator import InvestmentCalculator
from app.analyzers.sentiment_analyzer import SentimentAnalyzer
from config.settings import settings
from config.default import BUY_CATEGORIES, INTERVAL_MAP
from app.utils.bubble_registry import register as bubble_register
from app.managers.risk_manager import RiskManager

logging = setup_logger()

class BuyManager(BuyUseCase):
    """
    Gestor encargado de analizar y ejecutar compras de criptomonedas.
    """

    def __init__(
        self,
        data_provider: TradeDataProvider,
        executor: TradeExecutorPort,
        asset_filter: AssetFilter,
        quantity_calculator: QuantityCalculator,
        decision_engine: BuyDecisionEngine,
        investment_calculator: InvestmentCalculator,
        sentiment_analyzer: SentimentAnalyzer,
        max_records: int = settings.MAX_RECORDS,
        max_workers: int = settings.MAX_WORKERS
    ):
        self.data_provider = data_provider
        self.executor = executor
        self.asset_filter = asset_filter
        self.quantity_calculator = quantity_calculator
        self.decision_engine = decision_engine
        self.investment_calculator = investment_calculator
        self.sentiment_analyzer = sentiment_analyzer
        self.max_records = max_records
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        # Símbolos sin histórico válido para excluir de futuros análisis
        self.failed_symbols: Set[str] = set()
        # Risk management
        self.risk_manager = RiskManager(data_provider, executor)

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
        self, symbol: str, start_time: int, end_time: int, interval: str = settings.DEFAULT_CHECK_PRICE_INTERVAL
    ) -> List[List[Any]]:
        """
        Recopila todos los datos históricos para un símbolo dentro de un rango de tiempo.

        :param symbol: Símbolo de la criptomoneda (e.g., "BTCUSDC").
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
                data = self.data_provider.fetch_historical_data(
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
        logging.info(f"[{symbol}] Recopilando datos históricos...")
        try:
            data = self.fetch_all_data(symbol, start_time, end_time)
            logging.info(f"[{symbol}] Se han recopilado {len(data)} datos históricos.")

            if not data:
                return symbol, None

            analyzer = MarketAnalyzer(data, symbol)
            trend = analyzer.analyze()

            # Obtener indicadores técnicos
            sma_condition, rsi_condition, macd_condition, bb_condition, adx_condition, stochastic_condition = analyzer.get_signals()

            # Construir análisis inicial
            analysis = {
                'trend': trend,
                'indicators': {
                    'sma': sma_condition,
                    'rsi': rsi_condition,
                    'macd': macd_condition,
                    'bb': bb_condition,
                    'adx': adx_condition,
                    'stochastic': stochastic_condition
                },
                'bubble_override': analyzer.bubble_override,
                'sell_price_invalid': getattr(analyzer, 'sell_price_invalid', False),
                'sell_price_override': False
            }
            # Si precio de venta inválido y no override de burbuja, intentar con rango doble
            if analysis['sell_price_invalid'] and not analysis['bubble_override']:
                ext_hours = settings.DEFAULT_HISTORICAL_RANGE_HOURS * settings.DEFAULT_EXT_HISTORICAL_MULTIPLIER
                ext_days = ext_hours / 24
                now = datetime.now(timezone.utc)
                ext_start = int((now - timedelta(hours=ext_hours)).timestamp() * 1000)
                logging.info(
                    f"{symbol}: precio objetivo inválido, probando rango extendido: {ext_days:.0f}d ({ext_hours}h) x{settings.DEFAULT_EXT_HISTORICAL_MULTIPLIER}"
                )
                data_ext = self.fetch_all_data(symbol, ext_start, end_time)
                try:
                    analyzer2 = MarketAnalyzer(data_ext, symbol)
                    sell_price2 = analyzer2.calculate_sell_price(analyzer2._latest())
                    valid2 = analyzer2.is_sell_price_valid(sell_price2)
                    if valid2:
                        analysis['sell_price_override'] = True
                        logging.info(
                            f"{symbol}: override de precio válido tras extensión: objetivo {sell_price2:.6f} <= max ajustado"
                        )
                    else:
                        logging.info(
                            f"{symbol}: sigue inválido tras extensión: objetivo {sell_price2:.6f} > max ajustado"
                        )
                except Exception as e:
                    logging.error(f"Error reanalizando {symbol} con rango ext: {e}")
            return symbol, analysis
        except Exception as e:
            logging.error(f"Error procesando {symbol}: {e}")
            return symbol, None

    def analyze_and_execute_buys(self) -> None:
        """Orquesta el análisis técnico, filtra activos y decide compras."""
        # Recolectar análisis técnico (usando self._process_coin y thread_pool como antes)
        result: Dict[str, Dict[str, Any]] = {}

        now = datetime.now(timezone.utc)
        end_time = int(now.timestamp() * 1000)
        start_time = int((now - timedelta(hours=settings.DEFAULT_HISTORICAL_RANGE_HOURS)).timestamp() * 1000)

        # Preparar todas las monedas para procesar
        coins_to_process = []
        for cfg in BUY_CATEGORIES:
            method = getattr(self.data_provider, cfg['method'])
            logging.info(f"Procesando {cfg['name']}...")
            if 'min_price' in cfg and 'max_price' in cfg:
                coins = method(cfg['min_price'], cfg['max_price'], cfg.get('limit', 50))
            else:
                coins = method(cfg.get('limit', 50))
            # Si se obtienen menos monedas que el límite, rellenar con las más populares
            limit = cfg.get('limit', 50)
            if len(coins) < limit:
                logging.warning(f"Solo se obtuvieron {len(coins)} de {limit} para {cfg['name']}, rellenando con más populares")
                
            coins_to_process.extend(coins)
        # Excluir símbolos con datos históricos fallidos previos
        if self.failed_symbols:
            original = len(coins_to_process)
            coins_to_process = [c for c in coins_to_process if c['symbol'] not in self.failed_symbols]
            logging.debug(f"Se excluyeron {original - len(coins_to_process)} símbolos sin histórico previo.")
        logging.info(f"Se recuperaron {len(coins_to_process)} monedas para análisis técnico.")

        if not coins_to_process:
            logging.info("No hay monedas para procesar en esta ejecución.")
            return

        # Procesar cada moneda y actuar inmediatamente si hay señal
        logging.info(f"Procesando {len(coins_to_process)} monedas secuencialmente para análisis técnico.\n")
        for coin in coins_to_process:
            symbol, analysis = self._process_coin(coin, start_time, end_time)
            if not analysis:
                logging.warning(f"No histórico para {symbol}. Se excluirá en siguientes iteraciones.\n")
                self.failed_symbols.add(symbol)
                continue
            if not analysis.get('trend'):
                continue
            # Filtrar el activo
            if symbol not in self.asset_filter.filter([symbol]):
                continue
            # Obtener precio y saldo actual antes de cada decisión
            current_price = self.data_provider.get_price(symbol)
            usdc_balance = float(
                next((b['free'] for b in self.data_provider.get_balance_summary() if b['asset'] == 'USDC'), 0.0)
            )
            # Calcular asignación de capital según sentimiento
            # sentiment_score = self.sentiment_analyzer.get_overall_sentiment(symbol.replace("USDC", ""))
            # allocation = self.investment_calculator.calculate_size(usdc_balance, sentiment_score)
            quantity = self.quantity_calculator.calculate(symbol)
            if quantity <= 0:
                logging.info(f"Cantidad a comprar 0 para {symbol}")
                continue
            indicators = analysis.get('indicators', {})
            should = True # self.decision_engine.should_buy(symbol, current_price, quantity, indicators)
            # Permitir compra si override de burbuja o precio override
            if analysis.get('bubble_override') or analysis.get('sell_price_override') or should:
                # Verificar límites de exposición
                # if not self.risk_manager.can_open_position(current_price, quantity):
                #     logging.warning(f"{symbol}: no abre posición, límite de exposición alcanzado")
                #     continue
                # Ejecutar compra
                self._make_action(symbol, current_price, quantity)
                # Programar stop-loss/take-profit automáticos
                stop_pct = settings.STOP_LOSS_MARGIN / 100
                take_pct = settings.PROFIT_MARGIN / 100
                self.risk_manager.apply_stop_take(symbol, current_price, stop_pct, take_pct)
                # Registrar compra rápida si override de burbuja
                if analysis.get('bubble_override'):
                    bubble_register(symbol)
                # Esperar un poco para no saturar la API ni la cuenta
                time.sleep(5)

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