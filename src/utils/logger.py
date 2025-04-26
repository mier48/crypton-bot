import logging
import sys
import logging.handlers
import os
import typing

def setup_logger(name: str = 'binance_logger', level: typing.Union[str,int] = logging.INFO) -> logging.Logger:
    """
    Configura y devuelve un logger con el nombre y nivel especificados o según LOG_LEVEL env.
    """
    logger = logging.getLogger(name)
    # Determine level: env var overrides parameter
    lvl = os.getenv('LOG_LEVEL') or level
    if isinstance(lvl, str):
        lvl = getattr(logging, lvl.upper(), logging.INFO)
    logger.setLevel(lvl)

    # Evitar agregar múltiples handlers al logger
    if not logger.handlers:
        # Formato de logs
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Handler para la consola
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Handler rotativo para archivo
        rotating_handler = logging.handlers.RotatingFileHandler(
            'app.log', maxBytes=10*1024*1024, backupCount=5
        )
        rotating_handler.setFormatter(formatter)
        logger.addHandler(rotating_handler)

    return logger
