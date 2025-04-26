from prometheus_client import Counter, start_http_server

# Metrics counters
trades_executed_total = Counter('trades_executed_total', 'Total number of trades attempted')
trades_successful = Counter('trades_successful', 'Number of successful trades')
trades_failed = Counter('trades_failed', 'Number of failed trades')

def start_metrics_server(port: int) -> None:
    """Inicia el servidor HTTP para exponer métricas de Prometheus."""
    try:
        start_http_server(port)
    except OSError as e:
        import logging
        logging.getLogger(__name__).warning(
            f"No se pudo iniciar servidor de métricas en el puerto {port}: {e}"
        )
