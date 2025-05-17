import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple, Optional, Set

from concurrent.futures import ThreadPoolExecutor, as_completed
from prettytable import PrettyTable

from domain.ports import TradeDataProvider, TradeExecutorPort, BuyUseCase
from app.analyzers.market_analyzer import MarketAnalyzer
from app.services.asset_filter import AssetFilter
from app.services.quantity_calculator import QuantityCalculator
from app.services.buy_decision_engine import BuyDecisionEngine
from app.services.investment_calculator import InvestmentCalculator
from app.analyzers.sentiment_analyzer import SentimentAnalyzer
from config.settings import settings
from config.default import DEFAULT_INVESTMENT_AMOUNT
from config.default import BUY_CATEGORIES, INTERVAL_MAP
from app.utils.bubble_registry import register as bubble_register
from app.managers.risk_manager import RiskManager
from models.asset import Asset
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from config.database import SQLALCHEMY_DATABASE_URL

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

        # Configurar la conexión a la base de datos
        self.engine = create_engine(SQLALCHEMY_DATABASE_URL)

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
        Si no se pueden obtener datos con los parámetros de tiempo, intenta obtener los datos más recientes.

        :param symbol: Símbolo de la criptomoneda (e.g., "BTCUSDC").
        :param start_time: Tiempo de inicio en milisegundos.
        :param end_time: Tiempo de fin en milisegundos.
        :param interval: Intervalo de tiempo para los datos.
        :return: Lista de datos históricos.
        """
        all_data: List[List[Any]] = []
        interval_ms = self.calculate_interval_in_milliseconds(interval)
        max_attempts = 3
        
        def fetch_data_with_retries(symbol: str, start: Optional[int], end: Optional[int], interval: str) -> Tuple[bool, List[List[Any]]]:
            """Función auxiliar para reintentar la obtención de datos"""
            for attempt in range(max_attempts):
                try:
                    data = self.data_provider.fetch_historical_data(
                        symbol=symbol,
                        start_time=start,
                        end_time=end,
                        interval=interval
                    )
                    
                    if data:
                        return True, data
                        
                    if attempt < max_attempts - 1:  # No es el último intento
                        time.sleep(2)
                        
                except Exception as e:
                    logger.warning(f"Intento {attempt + 1} fallido para {symbol}: {e}")
                    if attempt < max_attempts - 1:  # No es el último intento
                        time.sleep(2)
                        
            return False, []
        
        # Primero intentamos con los parámetros de tiempo especificados
        success, data = fetch_data_with_retries(symbol, start_time, end_time, interval)
        
        if not success or not data:
            #logger.warning(f"No se pudieron obtener datos históricos para {symbol} con los parámetros de tiempo especificados. Intentando obtener los datos más recientes...")
            
            # Si falla, intentamos sin parámetros de tiempo para obtener los datos más recientes
            success, data = fetch_data_with_retries(symbol, None, None, interval)
            
            if not success or not data:
                #logger.error(f"No se pudieron obtener datos históricos para {symbol} ni siquiera sin parámetros de tiempo.")
                return []
                
            #logger.info(f"Se obtuvieron {len(data)} registros recientes para {symbol} (sin filtro de tiempo)")
            return data
            
        # Si llegamos aquí, tenemos datos con los parámetros de tiempo especificados
        all_data.extend(data)
        current_start = int(data[-1][6]) + interval_ms
        
        # Continuar obteniendo datos en bloques si es necesario
        while current_start < end_time:
            current_end = min(current_start + (interval_ms * self.max_records), end_time)
            
            success, data = fetch_data_with_retries(symbol, current_start, current_end, interval)
            
            if not data:
                logger.warning(f"No se pudieron obtener más datos históricos para {symbol} a partir de {current_start}")
                break
                
            all_data.extend(data)
            current_start = int(data[-1][6]) + interval_ms
            time.sleep(1)  # Pequeña pausa entre solicitudes
        
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
        #logger.info(f"[{symbol}] Recopilando datos históricos...")
        try:
            data = self.fetch_all_data(symbol, start_time, end_time)
            #logger.info(f"[{symbol}] Se han recopilado {len(data)} datos históricos.")

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
                logger.info(
                    f"{symbol}: precio objetivo inválido, probando rango extendido: {ext_days:.0f}d ({ext_hours}h) x{settings.DEFAULT_EXT_HISTORICAL_MULTIPLIER}"
                )
                data_ext = self.fetch_all_data(symbol, ext_start, end_time)
                try:
                    analyzer2 = MarketAnalyzer(data_ext, symbol)
                    sell_price2 = analyzer2.calculate_sell_price(analyzer2._latest())
                    valid2 = analyzer2.is_sell_price_valid(sell_price2)
                    if valid2:
                        analysis['sell_price_override'] = True
                        logger.info(
                            f"{symbol}: override de precio válido tras extensión: objetivo {sell_price2:.6f} <= max ajustado"
                        )
                    else:
                        logger.info(
                            f"{symbol}: sigue inválido tras extensión: objetivo {sell_price2:.6f} > max ajustado"
                        )
                except Exception as e:
                    logger.error(f"Error reanalizando {symbol} con rango ext: {e}")
            return symbol, analysis
        except Exception as e:
            logger.error(f"Error procesando {symbol}: {e}")
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
            logger.info(f"Procesando {cfg['name']}...")
            if 'min_price' in cfg and 'max_price' in cfg:
                coins = method(cfg['min_price'], cfg['max_price'], cfg.get('limit', 50))
            else:
                coins = method(cfg.get('limit', 50))
            # Si se obtienen menos monedas que el límite, rellenar con las más populares
            limit = cfg.get('limit', 50)
            if len(coins) < limit:
                logger.warning(f"Solo se obtuvieron {len(coins)} de {limit} para {cfg['name']}, rellenando con más populares")
                
            coins_to_process.extend(coins)
        # Excluir símbolos con datos históricos fallidos previos
        if self.failed_symbols:
            original = len(coins_to_process)
            coins_to_process = [c for c in coins_to_process if c['symbol'] not in self.failed_symbols]
            logger.debug(f"Se excluyeron {original - len(coins_to_process)} símbolos sin histórico previo.")
        logger.info(f"Se recuperaron {len(coins_to_process)} monedas para análisis técnico.")

        if not coins_to_process:
            logger.info("No hay monedas para procesar en esta ejecución.")
            return

        # Procesar cada moneda y actuar inmediatamente si hay señal
        logger.info(f"Procesando {len(coins_to_process)} monedas secuencialmente para análisis técnico.\n")
        for coin in coins_to_process:
            symbol, analysis = self._process_coin(coin, start_time, end_time)
            if not analysis:
                logger.warning(f"No histórico para {symbol}. Se excluirá en siguientes iteraciones.\n")
                self.failed_symbols.add(symbol)
                continue
            if not analysis.get('trend'):
                continue
            # Filtrar el activo
            if symbol not in self.asset_filter.filter([symbol]):
                continue
            # Verificar si ya existe el activo en la base de datos
            with Session(self.engine) as session:
                existing_asset = session.query(Asset).filter(Asset.symbol == symbol.replace('USDC', '')).first()
                if existing_asset:
                    logger.info(f"El activo {symbol} ya existe en la base de datos. Omitiendo compra.")
                    continue

            # Obtener precio y saldo actual antes de cada decisión
            current_price = self.data_provider.get_price(symbol)
            usdc_balance = float(
                next((b['free'] for b in self.data_provider.get_balance_summary() if b['asset'] == 'USDC'), 0.0)
            )
            
            quantity = self.quantity_calculator.calculate(symbol)
            if quantity <= 0:
                logger.info(f"Cantidad a comprar 0 para {symbol}")
                continue
                
            indicators = analysis.get('indicators', {})
            is_bubble = analysis.get('bubble_override', False)
            should = usdc_balance >= DEFAULT_INVESTMENT_AMOUNT  # self.decision_engine.should_buy(symbol, current_price, quantity, indicators)
            
            # Permitir compra si override de burbuja o precio override
            if is_bubble or analysis.get('sell_price_override') or should:
                # Verificar límites de exposición
                if not self.risk_manager.can_open_position(current_price, quantity):
                    logger.warning(f"{symbol}: no abre posición, límite de exposición alcanzado")
                    continue
                # Ejecutar compra
                if self._make_action(symbol, current_price, quantity, is_bubble):
                    # Programar stop-loss/take-profit automáticos
                    stop_pct = settings.STOP_LOSS_MARGIN / 100
                    take_pct = settings.PROFIT_MARGIN / 100
                    self.risk_manager.apply_stop_take(symbol, current_price, stop_pct, take_pct)
                    
                    # Registrar compra rápida si es burbuja
                    if is_bubble:
                        bubble_register(symbol)
                        logger.info(f"Compra de burbuja registrada para {symbol}")
                # Esperar un poco para no saturar la API ni la cuenta
                time.sleep(5)

    def _make_action(self, symbol: str, current_price: float, quantity_to_buy: float, is_bubble: bool = False) -> bool:
        """
        Ejecuta una orden de compra y guarda el activo en la base de datos.
        
        Args:
            symbol: Símbolo del activo (ej: 'BTCUSDC')
            current_price: Precio actual por unidad
            quantity_to_buy: Cantidad a comprar
            is_bubble: Indica si es una compra por burbuja
            
        Returns:
            bool: True si la operación fue exitosa, False en caso contrario
        """
        # Ejecutar la orden de compra
        trade_result = self.executor.execute_trade(
            side="BUY",
            symbol=symbol,
            order_type="MARKET",
            positions=quantity_to_buy,
            price=current_price,
            reason="BUBBLE_BUY" if is_bubble else "REGULAR_BUY",
        )

        if not trade_result:
            logger.error(f"Error al procesar la compra para {symbol}")
            return False
            
        logger.info(f"Orden de compra ejecutada para {symbol}.")
        
        try:
            # Guardar el activo en la base de datos
            with Session(self.engine) as session:
                asset = Asset(
                    symbol=symbol.replace('USDC', ''),  # Guardar solo el símbolo sin USDC
                    purchase_price=float(current_price),
                    amount=float(quantity_to_buy),
                    total_purchase_price=float(current_price) * float(quantity_to_buy),
                    is_bubble=is_bubble,
                    force_sell=is_bubble  # Si es burbuja, forzar venta en el futuro
                )
                session.add(asset)
                session.commit()
                logger.info(f"Activo {symbol} registrado en la base de datos")
                return True
                
        except Exception as e:
            logger.error(f"Error al guardar el activo {symbol} en la base de datos: {e}")
            try:
                session.rollback()
            except:
                pass
            return False