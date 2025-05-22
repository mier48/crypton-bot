import os
import time
from api.binance.data_manager import BinanceDataManager
from api.openai.client import OpenAIClient
from api.coingecko.client import CoinGeckoClient
from app.analyzers.sentiment_analyzer import SentimentAnalyzer
from app.analyzers.pre_trade_analyzer import PreTradeAnalyzer
from app.executors.trade_executor import TradeExecutor
from app.managers.buy_manager import BuyManager
from app.managers.sell_manager import SellManager
from app.notifiers.telegram_notifier import TelegramNotifier
from config.settings import settings
from app.services.asset_filter import AssetFilter
from app.services.quantity_calculator import QuantityCalculator
from app.services.buy_decision_engine import BuyDecisionEngine
from app.services.price_calculator import PriceCalculator
from app.services.sell_decision_engine import SellDecisionEngine
from app.services.investment_calculator import InvestmentCalculator
from app.strategies.loader import load_strategies  # Import plugin loader
from config.database import init_db
from utils.portfolio_initializer import PortfolioInitializer
from loguru import logger

from config.default import (
    DEFAULT_PROFIT_MARGIN,
    DEFAULT_SLEEP_INTERVAL,
    DEFAULT_INVESTMENT_AMOUNT,
    DEFAULT_STOP_LOSS_MARGIN,
    DEFAULT_USE_OPEN_AI_API
)


class TradeManager:
    """
    Clase para coordinar el análisis de tendencias y automatización de trading en el mercado de criptomonedas.
    """

    def __init__(
        self,
        max_records: int = 500,
        profit_margin: float = DEFAULT_PROFIT_MARGIN,
        stop_loss_margin: float = DEFAULT_STOP_LOSS_MARGIN,
        sleep_interval: int = DEFAULT_SLEEP_INTERVAL,
        investment_amount: float = DEFAULT_INVESTMENT_AMOUNT,
        use_open_ai_api: bool = DEFAULT_USE_OPEN_AI_API,
        max_workers: int = 10
    ):
        """
        Inicializa el TradeManager con todos los componentes necesarios.

        :param max_records: Número máximo de registros por solicitud.
        :param profit_margin: Margen de beneficio deseado en porcentaje.
        :param stop_loss_margin: Margen de stop loss en porcentaje.
        :param sleep_interval: Intervalo de espera entre ciclos de automatización en segundos.
        :param investment_amount: Monto de inversión por operación.
        :param max_workers: Número máximo de hilos para el ThreadPoolExecutor.
        """
        self.data_manager = BinanceDataManager()
        self.notifier = TelegramNotifier()
        self.executor = TradeExecutor()
        self.openai_client = OpenAIClient()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.coin_gecko_client = CoinGeckoClient()
        self.profit_margin = profit_margin
        self.stop_loss_margin = stop_loss_margin
        self.sleep_interval = sleep_interval
        self.investment_amount = investment_amount
        self.use_open_ai_api = use_open_ai_api
        self.running = False

        # Inicializar componentes de compra
        asset_filter = AssetFilter(self.data_manager, settings)
        quantity_calculator = QuantityCalculator(self.data_manager, settings)
        investment_calculator = InvestmentCalculator()
        buy_decision_engine = BuyDecisionEngine(
            self.openai_client,
            self.sentiment_analyzer,
            self.coin_gecko_client,
            self.data_manager
        )
        self.buy_manager = BuyManager(
            data_provider=self.data_manager,
            executor=self.executor,
            asset_filter=asset_filter,
            quantity_calculator=quantity_calculator,
            decision_engine=buy_decision_engine,
            investment_calculator=investment_calculator,
            sentiment_analyzer=self.sentiment_analyzer,
            max_records=max_records,
            max_workers=max_workers
        )

        # Inicializar componentes de venta
        price_calculator = PriceCalculator()
        sell_decision_engine = SellDecisionEngine(
            self.openai_client,
            self.sentiment_analyzer,
            self.coin_gecko_client,
            price_calculator
        )
        self.sell_manager = SellManager(
            data_provider=self.data_manager,
            executor=self.executor,
            sentiment_analyzer=self.sentiment_analyzer,
            price_calculator=price_calculator,
            decision_engine=sell_decision_engine,
            profit_margin=self.profit_margin,
            stop_loss_margin=self.stop_loss_margin,
            min_trade_usd=settings.MIN_TRADE_USD
        )
        # Cargar estrategias de plugins
        self.strategies = load_strategies(self.data_manager, settings)

    def has_available_funds(self) -> bool:
        """
        Verifica si hay fondos disponibles para realizar compras.
        
        Returns:
            bool: True si hay fondos disponibles, False en caso contrario.
        """
        try:
            # Obtener el balance de USDC
            balances = self.data_manager.get_balance_summary()
            usdc_balance = next((float(b['free']) for b in balances if b['asset'] == 'USDC'), 0.0)
            
            # Verificar si hay suficiente saldo para la inversión mínima
            has_funds = usdc_balance >= self.investment_amount
            
            if not has_funds:
                logger.warning(f"Sin fondos suficientes. Saldo USDC: {usdc_balance:.2f}, Mínimo requerido: {self.investment_amount:.2f}")
            
            return has_funds
            
        except Exception as e:
            logger.error(f"Error al verificar fondos disponibles: {e}")
            return False
            
    def is_market_trend_favorable(self) -> bool:
        """
        Analiza las tendencias de múltiples criptomonedas en las últimas horas.
        Si más del 75% de las criptomonedas tienen tendencia bajista, se considera
        que el mercado no es favorable para comprar.
        
        Returns:
            bool: True si la tendencia de mercado es favorable, False si es bajista.
        """
        try:
            # Lista de símbolos populares para analizar (se pueden ajustar según preferencias)
            symbols = ['BTCUSDC', 'ETHUSDC', 'BNBUSDC', 'XRPUSDC', 'ADAUSDC', 'SOLUSDC', 'DOTUSDC', 'AVAXUSDC']
            timeframe = '1h'
            period = 3  # Analizar las últimas 3 horas
            
            # Contador de tendencias bajistas
            bearish_count = 0
            total_analyzed = 0
            
            for symbol in symbols:
                try:
                    # Obtener datos de precio de las últimas horas
                    klines = self.data_manager.get_recent_klines(symbol, timeframe, period)
                    
                    if len(klines) >= period:
                        # Analizar si la tendencia es bajista comparando el precio de cierre
                        # del primer y último período
                        first_close = float(klines[0][4])  # Close price del primer período
                        last_close = float(klines[-1][4])  # Close price del último período
                        
                        if last_close < first_close:
                            bearish_count += 1
                            logger.debug(f"{symbol} muestra tendencia bajista en las últimas {period} horas")
                        else:
                            logger.debug(f"{symbol} muestra tendencia alcista o neutral en las últimas {period} horas")
                        
                        total_analyzed += 1
                except Exception as e:
                    logger.error(f"Error al analizar tendencia de {symbol}: {e}")
            
            # Si no se pudieron analizar suficientes símbolos, asumir que es seguro comprar
            if total_analyzed < 4:
                logger.warning(f"No se pudieron analizar suficientes símbolos ({total_analyzed}). Asumiendo mercado favorable.")
                return True
            
            # Calcular porcentaje de tendencias bajistas
            bearish_percentage = (bearish_count / total_analyzed) * 100
            is_favorable = bearish_percentage <= 75
            
            logger.info(f"Análisis de tendencia del mercado: {bearish_percentage:.1f}% de {total_analyzed} criptos analizadas muestran tendencia bajista.")
            if not is_favorable:
                logger.warning(f"Mercado desfavorable para compras: {bearish_percentage:.1f}% de símbolos en tendencia bajista supera el umbral del 75%.")
            
            return is_favorable
            
        except Exception as e:
            logger.error(f"Error al verificar tendencia del mercado: {e}")
            # En caso de error, permitir compras (mejor ser conservador)
            return True

    def run(self) -> None:
        """
        Inicia la automatización secuencial de ventas y compras.
        """
        self.running = True
        logger.info("Inicio de la automatización secuencial de ventas y compras.")
        logger.info("Condiciones de mercado favorables. Iniciando automatización secuencial.\n\n")
        try:
            while self.running:
                # Primero ejecutar ventas (siempre se ejecuta para liberar fondos)
                try:
                    self.sell_manager.analyze_and_execute_sells()
                except Exception as e:
                    logger.error(f"Error en análisis de venta: {e}")
                
                # Verificar fondos y tendencia del mercado antes de intentar comprar
                if self.has_available_funds() and self.is_market_trend_favorable():
                    try:
                        self.buy_manager.analyze_and_execute_buys()
                    except Exception as e:
                        logger.error(f"Error en análisis de compra: {e}")
                else:
                    logger.info("Omitiendo análisis de compras por fondos insuficientes")
                
                # Ejecutar ventas nuevamente por si se liberaron fondos con las compras
                try:
                    self.sell_manager.analyze_and_execute_sells()
                except Exception as e:
                    logger.error(f"Error en análisis de venta: {e}")
                
                # Reiniciar la base de datos antes de iniciar el siguiente ciclo
                self.reset_database()
                
                logger.warning(f"Bucle de compra y venta finalizado, esperando {self.sleep_interval} segundos.")
                time.sleep(self.sleep_interval)
                
        except KeyboardInterrupt:
            self.stop()
            logger.info("Automatización secuencial detenida por el usuario.")

    def stop(self) -> None:
        """
        Detiene la automatización combinada.
        """
        self.running = False
        logger.info("TradeManager detenido por señal externa.")

    def _buy_loop(self) -> None:
        """
        Loop que ejecuta comprobaciones de compra periódicamente.
        """
        while self.running:
            try:
                self.buy_manager.analyze_and_execute_buys()
            except Exception as e:
                logger.error(f"Error en buy loop: {e}")
            time.sleep(self.sleep_interval)

    def _sell_loop(self) -> None:
        """
        Loop que ejecuta comprobaciones de venta periódicamente.
        """
        while self.running:
            try:
                self.sell_manager.analyze_and_execute_sells()
            except Exception as e:
                logger.error(f"Error en sell loop: {e}")
            time.sleep(self.sleep_interval)
            
    def reset_database(self) -> None:
        """
        Reinicia la base de datos: borra todos los datos y vuelve a inicializarla.
        """
        try:
            logger.info("Reiniciando la base de datos...")
            
            # Obtener la ruta del archivo de base de datos
            db_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'crypton_bot.db')
            
            # Borrar el archivo si existe
            if os.path.exists(db_file):
                os.remove(db_file)
                logger.info("Base de datos existente eliminada.")
            
            # Inicializar la base de datos (crear tablas)
            from src.config.database import Base, engine
            Base.metadata.create_all(bind=engine)
            logger.info("Base de datos inicializada correctamente.")
            
            # Cargar el portafolio inicial
            initializer = PortfolioInitializer()
            initializer.initialize_portfolio()
            logger.info("Portafolio inicial cargado correctamente.")
            
        except Exception as e:
            logger.error(f"Error al reiniciar la base de datos: {e}")
