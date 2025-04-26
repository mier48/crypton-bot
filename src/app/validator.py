from typing import Optional, Dict, Any
from utils.logger import setup_logger
from config.default import DEFAULT_LOT_SIZE_FILTER as LOT_SIZE_FILTER

logger = setup_logger(__name__)

def get_decimals_for_symbol(symbol_data: Dict[str, Any], symbol_name: str) -> Optional[int]:
    """
    Determines the number of allowed decimals for a symbol based on the LOT_SIZE filter.

    Args:
        symbol_data (dict): Binance API data (full response).
        symbol_name (str): Symbol name, e.g., "BTCUSDC".

    Returns:
        int: Number of allowed decimals for the quantity.
        None: If the symbol is not found or the number of decimals cannot be determined.
    """
    try:
        # Validate data structure
        symbols = symbol_data.get("symbols", [])
        if not isinstance(symbols, list):
            logger.error("Invalid structure in symbol_data: does not contain a list of symbols.")
            return None

        # Search for the specific symbol
        for symbol in symbols:
            if symbol.get("symbol") == symbol_name:
                # Look for the LOT_SIZE filter
                filters = symbol.get("filters", [])
                if not isinstance(filters, list):
                    logger.error(f"Invalid structure in filters for symbol {symbol_name}.")
                    return None

                for filter_item in filters:
                    if filter_item.get("filterType") == LOT_SIZE_FILTER:
                        step_size = filter_item.get("stepSize", "1.00")
                        if isinstance(step_size, str) and "." in step_size:
                            # Count significant decimals
                            return len(step_size.split(".")[1].rstrip("0"))
                        return 0  # No decimals if stepSize is an integer

        logger.warning(f"Symbol {symbol_name} or filter {LOT_SIZE_FILTER} not found.")
        return None

    except Exception as e:
        logger.exception(f"Error retrieving decimals for symbol {symbol_name}: {e}")
        return None
