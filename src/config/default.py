from typing import Dict

DEFAULT_PROFIT_MARGIN = 3 # 3% profit margin
DEFAULT_SLEEP_INTERVAL = 90 # 90 seconds wait interval
DEFAULT_INVESTMENT_AMOUNT = 20 # $20 investment per trade (ajustado según usuario)
DEFAULT_MAX_BUY_PRICE = 5 # $5 maximum unit purchase price (fijo)
DEFAULT_LOT_SIZE_FILTER = "LOT_SIZE" # Lot size filter
DEFAULT_VALIDATION_MIN_SCORE = 3 # Minimum validation score (reducido para ser menos estricto)
DEFAULT_STOP_LOSS_MARGIN = 15 # 25% stop loss margin
DEFAULT_CHECK_PRICE_INTERVAL = "5m" # 5-minute price interval for scalping rápido
DEFAULT_HISTORICAL_RANGE_HOURS = 24  # 4-hour histórico ajustado para trading rápido
DEFAULT_EXT_HISTORICAL_MULTIPLIER = 2  # Multiplier for extended historical range during sell_price validation
DEFAULT_USE_OPEN_AI_API = False # Do not use OpenAI API by default
DEFAULT_MAX_EXPOSURE_PERCENT = 50  # Porcentaje máximo de exposición total (0-100)
DEFAULT_RISK_PER_TRADE_PERCENT = 2  # Porcentaje de capital arriesgado por operación (0-100)

# Bubble detection
BUBBLE_DETECT_WINDOW = 12  # Número de velas para medir crecimiento (ej. últimas 12 barras de 5m = 1h)
BUBBLE_MAX_GROWTH = 0.05  # Crecimiento máximo permitido en la ventana (5%)
BUBBLE_MOMENTUM_WINDOW = 24  # Número de velas para momentum (ej. 2h a 5m = 24 barras)
BUBBLE_MOMENTUM_THRESHOLD = 0.5  # 50% de velas alcistas para override de burbuja

INTERVAL_MAP: Dict[str, int] = {
    # Seconds
    "1s": 1_000,                  # 1 second
    
    # Minutes
    "1m": 60_000,                 # 1 minute
    "3m": 3 * 60_000,             # 3 minutes
    "5m": 5 * 60_000,             # 5 minutes
    "15m": 15 * 60_000,           # 15 minutes
    "30m": 30 * 60_000,           # 30 minutes
    
    # Hours 
    "1h": 3_600_000,              # 1 hour
    "2h": 2 * 3_600_000,          # 2 hours
    "4h": 4 * 3_600_000,          # 4 hours
    "6h": 6 * 3_600_000,          # 6 hours
    "8h": 8 * 3_600_000,          # 8 hours
    "12h": 12 * 3_600_000,        # 12 hours
    
    # Days
    "1d": 86_400_000,             # 1 day
    "3d": 3 * 86_400_000,         # 3 days
    
    # Weeks
    "1w": 7 * 86_400_000,         # 1 week
    
    # Months (approximation: 30 days in a month)
    "1M": 30 * 86_400_000         # 1 month (~30 days)
}

BUY_CATEGORIES = [
    {
        "name": "Top 50 Gainers",
        "method": "get_top_gainers",
        "limit": 50
    },
    {
        "name": "Top 20 Losers",
        "method": "get_top_losers",
        "limit": 20
    },
    {
        "name": "Top 10 Most Popular",
        "method": "get_most_popular",
        "limit": 10
    },
    {
        "name": "Top 10 Popular Mid Price",
        "method": "get_popular_mid_price",
        "limit": 10
    },
    {
        "name": "Top 10 Popular Low Price",
        "method": "get_popular_low_price",
        "limit": 10
    },
    {
        "name": "Top 10 Popular Extra Low Price",
        "method": "get_popular_extra_low_price",
        "limit": 10
    },
    {
        "name": "Popular Price Range $2.5 - $5",
        "method": "get_popular_by_price_range",
        "limit": 50,
        "min_price": 2.5,
        "max_price": 5
    },
    {
        "name": "Popular Price Range $1 - $2.5",
        "method": "get_popular_by_price_range",
        "limit": 50,
        "min_price": 1,
        "max_price": 2.5
    },
    {
        "name": "Popular Price Range $0.5 - $1.0",
        "method": "get_popular_by_price_range",
        "limit": 50,
        "min_price": 0.5,
        "max_price": 1.0
    },
    {
        "name": "Popular Price Range $0.01 - $0.1",
        "method": "get_popular_by_price_range",
        "limit": 20,
        "min_price": 0.01,
        "max_price": 0.1
    }
]

# Parámetros para MarketAnalyzer (antes hardcodeados en la clase)
SMA_SHORT_PERIOD = 10
SMA_LONG_PERIOD = 50
EMA_PERIOD = 20
RSI_PERIOD = 14
MACD_SHORT_PERIOD = 12
MACD_LONG_PERIOD = 26
MACD_SIGNAL_PERIOD = 9
BB_PERIOD = 20
BB_STD_DEV = 2
ADX_PERIOD = 14
STOCHASTIC_PERIOD = 14

# Umbrales de señal de compra
BUY_THRESHOLD_SMA = 0.001  # Diferencia relativa entre SMA corto y largo
BUY_THRESHOLD_RSI = 30
BUY_THRESHOLD_MACD = 0    # MACD > señal
BUY_THRESHOLD_BB = 'lower'
BUY_THRESHOLD_ADX = 25
BUY_THRESHOLD_STOCHASTIC = 20

# Puntuación mínima de indicadores para señal de compra
DEFAULT_VALIDATION_MIN_SCORE = 3
