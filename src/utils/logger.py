import logging
import sys

def setup_logger(name: str = 'binance_logger', level: int = logging.INFO) -> logging.Logger:
    """
    Configura y devuelve un logger con el nombre y nivel especificados.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Evitar agregar múltiples handlers al logger
    if not logger.handlers:
        # Formato de logs
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Handler para la consola
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Handler para archivo (opcional)
        file_handler = logging.FileHandler('binance_api.log')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
