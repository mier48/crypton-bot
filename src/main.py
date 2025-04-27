from app.managers.trade_manager import TradeManager
from config.settings import settings
import signal
from utils.metrics import start_metrics_server
from utils.logger import setup_logger
import threading
import time
from datetime import datetime

logger = setup_logger(__name__)

def notification_loop(data_manager, notifier, interval_minutes):
    """
    Loop para enviar balance de portafolio vía Telegram cada interval_minutes minutos.
    """
    while True:
        try:
            balances = data_manager.get_balance_summary()
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
            # Tabla monoespaciada
            lines = [f" *Resumen de Balances* ({now_str})", "```", f"{'Activo':<10} {'Libre':>12} {'Bloqueado':>12}"]
            for b in balances:
                asset = b.get("asset")
                free = float(b.get("free", 0))
                locked = float(b.get("locked", 0))
                lines.append(f"{asset:<10} {free:>12.6f} {locked:>12.6f}")
            lines.append("```")
            message = "\n".join(lines)
            notifier.send_message(message)
        except Exception as e:
            logger.exception(f"Error en notificación de balance: {e}")
        time.sleep(interval_minutes * 60)

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
    # Iniciar hilo de notificaciones periódicas (cada 90 minutos)
    threading.Thread(
        target=notification_loop,
        args=(trade_manager.data_manager, trade_manager.notifier, 90),
        daemon=True
    ).start()
    trade_manager.run()

if __name__ == "__main__":
    main()
