from prometheus_client import Counter, start_http_server

# Metrics counters
trades_executed_total = Counter('trades_executed_total', 'Total number of trades attempted')
trades_successful = Counter('trades_successful', 'Number of successful trades')
trades_failed = Counter('trades_failed', 'Number of failed trades')

def start_metrics_server(port: int, max_attempts: int = 5) -> None:
    """
    Inicia el servidor HTTP para exponer métricas de Prometheus.
    Intenta con puertos alternativos si el puerto especificado está ocupado.
    """
    import socket
    import logging
    logger = logging.getLogger(__name__)
    
    for attempt in range(max_attempts):
        current_port = port + attempt
        try:
            # Intentar conectar al puerto para ver si está disponible
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', current_port))
            
            # Si llegamos aquí, el puerto está disponible
            start_http_server(current_port)
            logger.info(f"Servidor de métricas iniciado en el puerto {current_port}")
            return
            
        except OSError as e:
            if attempt == max_attempts - 1:  # Último intento
                logger.warning(
                    f"No se pudo iniciar el servidor de métricas en ningún puerto "
                    f"entre {port} y {port + max_attempts - 1}: {e}"
                )
            else:
                logger.debug(f"Puerto {current_port} ocupado, intentando con {current_port + 1}...")
