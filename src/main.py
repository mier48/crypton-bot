from app.managers.trade_manager import TradeManager
from config.settings import settings
import signal
from utils.metrics import start_metrics_server
from utils.logger import setup_logger

logger = setup_logger(__name__)

def main() -> None:
    # Iniciar servidor de métricas
    start_metrics_server(settings.METRICS_PORT)

    # Configurar TradeManager con settings de Pydantic
    trade_manager = TradeManager(
        max_records=settings.MAX_RECORDS,
        profit_margin=settings.PROFIT_MARGIN,
        stop_loss_margin=settings.STOP_LOSS_MARGIN,
        sleep_interval=settings.SLEEP_INTERVAL,
        investment_amount=settings.INVESTMENT_AMOUNT,
        max_workers=settings.MAX_WORKERS,
        use_open_ai_api=settings.USE_OPEN_AI_API
    )

    # Manejo de señales para shutdown limpio
    # signal.signal(signal.SIGINT, lambda s, f: trade_manager.stop())  # Ctrl-C manejará KeyboardInterrupt internamente
    signal.signal(signal.SIGTERM, lambda s, f: trade_manager.stop())

    logger.info("Iniciando Crypton Bot...")
    trade_manager.run()

if __name__ == "__main__":
    main()
