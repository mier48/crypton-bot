import time
from utils.logger import setup_logger

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

from config.default import (
    DEFAULT_PROFIT_MARGIN,
    DEFAULT_SLEEP_INTERVAL,
    DEFAULT_INVESTMENT_AMOUNT,
    DEFAULT_STOP_LOSS_MARGIN,
    DEFAULT_USE_OPEN_AI_API
)

logging = setup_logger()

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

    def run(self) -> None:
        """
        Inicia la automatización secuencial de ventas y compras.
        """
        self.running = True
        logging.info("Inicio de la automatización secuencial de ventas y compras.")
        logging.info("Condiciones de mercado favorables. Iniciando automatización secuencial.\n\n")
        try:
            while self.running:
                # Primero ejecutar ventas, luego compras
                try:
                    self.sell_manager.analyze_and_execute_sells()
                except Exception as e:
                    logging.error(f"Error en análisis de venta: {e}")
                try:
                    self.buy_manager.analyze_and_execute_buys()
                except Exception as e:
                    logging.error(f"Error en análisis de compra: {e}")
                # # Ejecutar estrategias pluginizadas
                # for strat in self.strategies:
                #     try:
                #         signals = strat.analyze()
                #         symbol = signals.get('symbol')
                #         size = signals.get('size', self.investment_amount)
                #         order_type = signals.get('order_type', 'MARKET')
                #         # Señal de compra
                #         if signals.get('buy') and symbol:
                #             self.executor.execute_trade(
                #                 'BUY', symbol, order_type, size,
                #                 reason=f"{strat.name()} buy"
                #             )
                #         # Señal de venta
                #         if signals.get('sell') and symbol:
                #             self.executor.execute_trade(
                #                 'SELL', symbol, order_type, size,
                #                 reason=f"{strat.name()} sell"
                #             )
                #     except Exception as e:
                #         logging.error(f"Error en estrategia {strat.name()}: {e}")
                logging.warning(f"Bucle de compra y venta finalizado, esperando {self.sleep_interval} segundos.")
                # Enviar balance vía Telegram
                # try:
                #     balances = self.data_manager.get_balance_summary()
                #     lines = ["*Resumen de balances:*"]
                #     for b in balances:
                #         asset = b.get("asset")
                #         free = float(b.get("free", 0))
                #         locked = float(b.get("locked", 0))
                #         lines.append(f"🔹 *{asset}:* Libre `{free:.6f}`, Bloqueado `{locked:.6f}`")
                #     message = "\n".join(lines)
                #     self.notifier.send_message(message)
                # except Exception as e:
                #     logging.exception(f"Error al enviar balance: {e}")
                time.sleep(self.sleep_interval)
        except KeyboardInterrupt:
            self.stop()
            logging.info("Automatización secuencial detenida por el usuario.")

    def stop(self) -> None:
        """
        Detiene la automatización combinada.
        """
        self.running = False
        logging.info("TradeManager detenido por señal externa.")

    def _buy_loop(self) -> None:
        """
        Loop que ejecuta comprobaciones de compra periódicamente.
        """
        while self.running:
            try:
                self.buy_manager.analyze_and_execute_buys()
            except Exception as e:
                logging.error(f"Error en buy loop: {e}")
            time.sleep(self.sleep_interval)

    def _sell_loop(self) -> None:
        """
        Loop que ejecuta comprobaciones de venta periódicamente.
        """
        while self.running:
            try:
                self.sell_manager.analyze_and_execute_sells()
            except Exception as e:
                logging.error(f"Error en sell loop: {e}")
            time.sleep(self.sleep_interval)
