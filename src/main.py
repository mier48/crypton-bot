import os
import sys
import signal
import threading
import time

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.config.database import init_db
from src.utils.portfolio_initializer import PortfolioInitializer
from src.utils.metrics import start_metrics_server
from loguru import logger
from src.app.managers.trade_manager import TradeManager
from src.app.portfolio.manager import PortfolioManager
from src.app.notifications.portfolio_notifier import start_portfolio_notifier
from src.app.market_cycles.strategy_manager import AdaptiveStrategyManager

def initialize_database() -> None:
    """Inicializa la base de datos y carga el portafolio inicial si es necesario"""
    try:
        # Verificar si la base de datos ya está inicializada
        db_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'crypton_bot.db')
        db_exists = os.path.exists(db_file)
        
        # Inicializar la base de datos
        init_db()
        
        # Si la base de datos no existía o está vacía, cargar el portafolio inicial
        if not db_exists or not db_file:
            logger.info("Base de datos nueva detectada. Inicializando con portafolio de Binance...")
            initializer = PortfolioInitializer()
            initializer.initialize_portfolio()
        else:
            logger.info("Base de datos ya inicializada. No se realizará ninguna acción.")
    except Exception as e:
        logger.error(f"Error al inicializar la base de datos: {e}")

def main():
    # Obtener el modo de ejecución desde la configuración
    execution_mode = settings.EXECUTION_MODE
    
    # Validar que el modo de ejecución sea válido
    if execution_mode not in ['trade', 'portfolio', 'full']:
        logger.warning(f"Modo de ejecución '{execution_mode}' no válido. Utilizando 'full' como predeterminado.")
        execution_mode = 'full'
    
    # Inicializar la base de datos
    initialize_database()
    
    # Iniciar el servidor de métricas
    start_metrics_server(port=settings.METRICS_PORT)
    
    # Inicializar el gestor de trading si es necesario
    trade_manager = None
    if execution_mode in ['trade', 'full']:
        trade_manager = TradeManager(
            max_records=settings.MAX_RECORDS,
            profit_margin=settings.PROFIT_MARGIN,
            stop_loss_margin=settings.STOP_LOSS_MARGIN,
            sleep_interval=settings.SLEEP_INTERVAL,
            investment_amount=settings.INVESTMENT_AMOUNT,
            max_workers=settings.MAX_WORKERS,
            use_open_ai_api=settings.USE_OPEN_AI_API
        )
        
    # Inicializar el optimizador de portfolio si es necesario
    portfolio_manager = None
    if execution_mode in ['portfolio', 'full']:
        # Para el portfolio manager modular solo necesitamos el data_manager
        data_manager = trade_manager.data_manager if trade_manager else None
        
        # Si estamos en modo portfolio sin trade_manager, creamos una instancia nueva
        if not data_manager:
            from src.api.binance.data_manager import BinanceDataManager
            data_manager = BinanceDataManager()
        
        # Inicializar el portfolio manager modular
        portfolio_manager = PortfolioManager(data_manager=data_manager)

    # Configurar el manejador de señales para apagado limpio
    def signal_handler(signum, frame):
        logger.info("Recibida señal de terminación, cerrando...")
        if trade_manager:
            trade_manager.stop()
        if portfolio_manager:
            portfolio_manager.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Inicializar el sistema de adaptación a ciclos de mercado si está habilitado
    market_cycle_manager = None
    if settings.ENABLE_MARKET_CYCLE_ADAPTATION:
        try:
            # Usar el mismo data_manager para mantener la coherencia
            market_data_manager = data_manager
            market_cycle_manager = AdaptiveStrategyManager(market_data_manager)
            
            # Forzar una primera actualización del ciclo de mercado al inicio
            cycle_info = market_cycle_manager.update_market_state(force=True)
            current_cycle = cycle_info.get('market_cycle', {}).get('current', 'unknown')
            logger.info(f"Sistema de adaptación a ciclos de mercado inicializado (ciclo actual: {current_cycle})")
            
            # Compartir el market_cycle_manager con el risk_manager para las adaptaciones
            if trade_manager and hasattr(trade_manager, 'risk_manager'):
                trade_manager.risk_manager.strategy_manager = market_cycle_manager
                logger.info("Integrado sistema de adaptación con el gestor de riesgos")
                
            # Compartir con el portfolio_manager si es necesario
            if portfolio_manager:
                # Conectar el portfolio_manager con el sistema de adaptación
                if hasattr(portfolio_manager, 'set_strategy_manager'):
                    portfolio_manager.set_strategy_manager(market_cycle_manager)
                    logger.info("Integrado sistema de adaptación con el gestor de portafolio")
        except Exception as e:
            logger.error(f"Error al inicializar el sistema de adaptación a ciclos de mercado: {e}")
    else:
        logger.info("Sistema de adaptación a ciclos de mercado desactivado en la configuración")
        
    # Iniciar servicios y managers en hilos separados
    threads = []
    
    # Iniciar el notificador de portafolio
    if trade_manager:
        notification_thread = threading.Thread(
            target=start_portfolio_notifier,
            args=(trade_manager.data_manager, trade_manager.notifier, 180),  # 3 horas
            daemon=True
        )
        notification_thread.start()
        threads.append(notification_thread)
        
    # Hilo para actualizar periódicamente el ciclo de mercado
    if market_cycle_manager:
        update_interval = settings.MARKET_CYCLE_UPDATE_INTERVAL * 3600  # Convertir horas a segundos
        
        def update_market_cycle_periodically():
            while True:
                try:
                    # Dormir durante el intervalo configurado
                    time.sleep(update_interval)
                    
                    # Actualizar el ciclo de mercado
                    adaptations = market_cycle_manager.update_market_state()
                    current_cycle = adaptations.get('market_cycle', {}).get('current', 'unknown')
                    logger.info(f"Ciclo de mercado actualizado automáticamente: {current_cycle}")
                except Exception as e:
                    logger.error(f"Error al actualizar ciclo de mercado: {e}")
                    time.sleep(300)  # Esperar 5 minutos antes de reintentar en caso de error
        
        # Iniciar el hilo de actualización del ciclo de mercado
        market_cycle_thread = threading.Thread(
            target=update_market_cycle_periodically,
            daemon=True
        )
        market_cycle_thread.start()
        threads.append(market_cycle_thread)
        logger.info(f"Actualización automática de ciclos de mercado programada cada {settings.MARKET_CYCLE_UPDATE_INTERVAL} horas")
    
    # Hilo para el portfolio manager
    if portfolio_manager:
        portfolio_thread = threading.Thread(
            target=portfolio_manager.start,
            daemon=True
        )
        portfolio_thread.start()
        threads.append(portfolio_thread)
        logger.info("Sistema de optimización de portafolio iniciado")
    
    logger.info(f"Crypton Bot iniciado en modo: {execution_mode}")
    
    # Iniciar el gestor de trading en el hilo principal si está activo
    if trade_manager:
        try:
            trade_manager.run()
        except KeyboardInterrupt:
            logger.info("Deteniendo el bot...")
            trade_manager.stop()
    else:
        # Si no hay trade_manager, mantener el hilo principal activo
        try:
            # Mantener el proceso principal vivo mientras los hilos trabajan
            while True:
                signal.pause()
        except KeyboardInterrupt:
            logger.info("Deteniendo el bot...")
            if portfolio_manager:
                portfolio_manager.stop()
    # trade_manager.run()

if __name__ == "__main__":
    main()
