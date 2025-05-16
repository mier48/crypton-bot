from app.managers.trade_manager import TradeManager
from config.settings import settings
import signal
from utils.metrics import start_metrics_server
from utils.logger import setup_logger
import threading
import time
from datetime import datetime, timezone

logger = setup_logger(__name__)

def notification_loop(data_manager, notifier, interval_minutes=60):
    """
    Envía notificaciones periódicas con el estado del portafolio.
    
    Args:
        data_manager: Instancia de BinanceDataManager para obtener datos de la cuenta
        notifier: Instancia de TelegramNotifier para enviar notificaciones
        interval_minutes: Intervalo en minutos entre notificaciones
    """
    while True:
        try:
            # Obtener resumen de saldos
            balances = data_manager.get_balance_summary()
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            
            # Construir mensaje
            lines = [f"🔄 *Actualizado: {now_str}*\n"]
            
            # Sección de saldos
            lines.append("💰 *Saldos*")
            
            # Mostrar primero USDC si está presente
            usdc_balance = next((b for b in balances if b['asset'] == 'USDC'), None)
            if usdc_balance:
                free = float(usdc_balance.get('free', 0))
                if free >= 1:
                    lines.append(f"🔹 *USDC*: {free}")
            
            # Filtrar activos con saldo (excluyendo USDC ya mostrado)
            assets_with_balance = [
                b for b in balances 
                if b['asset'] != 'USDC' and 
                (float(b.get('free', 0)) >= 1 or float(b.get('locked', 0)) >= 1)
            ]
            
            # Ordenar por valor total (libre + bloqueado) descendente
            assets_with_balance.sort(
                key=lambda x: float(x.get('free', 0)),
                reverse=True
            )
            
            # Mostrar otros activos
            for b in assets_with_balance:
                asset = b['asset']
                free = float(b.get('free', 0))
                lines.append(f"🔹 *{asset}*: {free}")
            
            # Enviar mensaje
            message = "\n" + "\n".join(lines) + "\n"
            notifier.send_message(message)
            
        except Exception as e:
            logger.error(f"Error en notificación periódica: {e}")
        
        # Esperar hasta la próxima notificación
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
    # Iniciar hilo de notificaciones periódicas (cada 180 minutos)
    threading.Thread(
        target=notification_loop,
        args=(trade_manager.data_manager, trade_manager.notifier, 180),
        daemon=True
    ).start()
    trade_manager.run()

if __name__ == "__main__":
    main()
