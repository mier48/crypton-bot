import time
from concurrent.futures import ThreadPoolExecutor
from utils.logger import setup_logger

from api.binance.data_manager import BinanceDataManager
from api.openai.client import OpenAIClient
from api.coingecko.client import CoinGeckoClient
from app.analyzers.sentiment_analyzer import SentimentAnalyzer
from app.analyzers.pre_trade_analyzer import PreTradeAnalyzer
from app.executors.trade_executor import TradeExecutor
from app.managers.buy_manager import BuyManager
from app.managers.sell_manager import SellManager
from app.notifier import TelegramNotifier

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

        # Inicializar gestores de compra y venta
        self.buy_manager = BuyManager(
            data_manager=self.data_manager,
            executor=self.executor,
            openai_client=self.openai_client,
            sentiment_analyzer=self.sentiment_analyzer,
            coin_gecko_client=self.coin_gecko_client,
            profit_margin=self.profit_margin,
            stop_loss_margin=self.stop_loss_margin,
            investment_amount=self.investment_amount,
            use_open_ai_api=self.use_open_ai_api,
            max_records=max_records,
            max_workers=max_workers
        )

        self.sell_manager = SellManager(
            data_manager=self.data_manager,
            executor=self.executor,
            sentiment_analyzer=self.sentiment_analyzer,
            coin_gecko_client=self.coin_gecko_client,
            openai_client=self.openai_client,
            profit_margin=self.profit_margin,
            stop_loss_margin=self.stop_loss_margin,
            use_open_ai_api=self.use_open_ai_api,
        )

    def run(self) -> None:
        """
        Inicia el proceso combinado de análisis de tendencias para comprar y automatización de ventas para vender.
        """
        self.running = True
        logging.info("Inicio de la automatización combinada de compras y ventas.")

        # pre_trade_analyzer = PreTradeAnalyzer()

        # should_trade, reason = pre_trade_analyzer.should_trade()

        # while True:
        # if should_trade:
        logging.info("Condiciones de mercado favorables. Iniciando automatización\n\n")

        with ThreadPoolExecutor(max_workers=2) as executor:
            while self.running:
                try:
                    # Ejecutar análisis de compra y venta en paralelo
                    executor.submit(self.buy_manager.analyze_and_execute_buys)
                    executor.submit(self.sell_manager.analyze_and_execute_sells)

                    time.sleep(self.sleep_interval)

                except KeyboardInterrupt:
                    self.running = False
                    logging.info("Automatización combinada detenida por el usuario.")

                except Exception as e:
                    self.running = False
                    logging.error(f"Error en la automatización combinada: {e}")
        # else:
            # logging.info(f"No se realizarán operaciones: {reason}")
                # time.sleep(60*30) # Esperar 30 minutos antes de volver a verificar las condiciones del mercado
