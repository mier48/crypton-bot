from typing import Optional, Dict, Any
from utils.logger import setup_logger
from config.default import DEFAULT_LOT_SIZE_FILTER as LOT_SIZE_FILTER

logger = setup_logger(__name__)

def get_decimals_for_symbol(symbol_data: Dict[str, Any], symbol_name: str) -> Optional[int]:
    """
    Determina la cantidad de decimales permitidos para un símbolo en función del filtro LOT_SIZE.

    Args:
        symbol_data (dict): Datos de la API de Binance (respuesta completa).
        symbol_name (str): Nombre del símbolo, por ejemplo, "BTCUSDT".

    Returns:
        int: Número de decimales permitidos para la cantidad.
        None: Si no se encuentra el símbolo o no se puede determinar el número de decimales.
    """
    try:
        # Validar la estructura de los datos
        symbols = symbol_data.get("symbols", [])
        if not isinstance(symbols, list):
            logger.error("Estructura inválida en symbol_data: no contiene una lista de símbolos.")
            return None

        # Buscar el símbolo específico
        for symbol in symbols:
            if symbol.get("symbol") == symbol_name:
                # Buscar el filtro LOT_SIZE
                filters = symbol.get("filters", [])
                if not isinstance(filters, list):
                    logger.error(f"Estructura inválida en los filtros para el símbolo {symbol_name}.")
                    return None

                for filter_item in filters:
                    if filter_item.get("filterType") == LOT_SIZE_FILTER:
                        step_size = filter_item.get("stepSize", "1.00")
                        if isinstance(step_size, str) and "." in step_size:
                            # Contar los decimales significativos
                            return len(step_size.split(".")[1].rstrip("0"))
                        return 0  # Sin decimales si stepSize es un número entero

        logger.warning(f"No se encontró el símbolo {symbol_name} o el filtro {LOT_SIZE_FILTER}.")
        return None

    except Exception as e:
        logger.exception(f"Error al obtener decimales para el símbolo {symbol_name}: {e}")
        return None
