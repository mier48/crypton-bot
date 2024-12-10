from typing import Dict

DEFAULT_PROFIT_MARGIN = 0.5
DEFAULT_SLEEP_INTERVAL = 90
DEFAULT_INVESTMENT_AMOUNT = 25
DEFAULT_MAX_BUY_PRICE = 5
DEFAULT_LOT_SIZE_FILTER = "LOT_SIZE"
DEFAULT_VALIDATION_MIN_SCORE = 5
DEFAULT_STOP_LOSS_MARGIN = 12
DEFAULT_CHECK_PRICE_INTERVAL = "5m"
DEFAULT_HISTORICAL_RANGE_HOURS = 5 * 24 # 7 días
DEFAULT_USE_OPEN_AI_API = False

INTERVAL_MAP: Dict[str, int] = {
    # Seconds
    "1s": 1_000,                  # 1 segundo
    
    # Minutes
    "1m": 60_000,                 # 1 minuto
    "3m": 3 * 60_000,             # 3 minutos
    "5m": 5 * 60_000,             # 5 minutos
    "15m": 15 * 60_000,           # 15 minutos
    "30m": 30 * 60_000,           # 30 minutos
    
    # Hours
    "1h": 3_600_000,              # 1 hora
    "2h": 2 * 3_600_000,          # 2 horas
    "4h": 4 * 3_600_000,          # 4 horas
    "6h": 6 * 3_600_000,          # 6 horas
    "8h": 8 * 3_600_000,          # 8 horas
    "12h": 12 * 3_600_000,        # 12 horas
    
    # Days
    "1d": 86_400_000,             # 1 día
    "3d": 3 * 86_400_000,         # 3 días
    
    # Weeks
    "1w": 7 * 86_400_000,         # 1 semana
    
    # Months (approximation: 30 days in a month)
    "1M": 30 * 86_400_000         # 1 mes (~30 días)
}

BUY_CATEGORIES = [
    {
        "name": "Top 50 Gainers",
        "method": "get_top_gainers",
        "limit": 50
    },
    {
        "name": "Top 20 Más Populares (precio entre $2.5 y $5)",
        "method": "get_popular_by_price_range",
        "limit": 40,
        "min_price": 2.5,
        "max_price": 5,
    },
    {
        "name": "Top 20 Más Populares (precio entre $1 y $2.5)",
        "method": "get_popular_by_price_range",
        "limit": 30,
        "min_price": 1,
        "max_price": 2.5,
    },
    {
        "name": "Top 20 Más Populares (precio entre $0.1 y $1.0)",
        "method": "get_popular_by_price_range",
        "limit": 20,
        "min_price": 0.1,
        "max_price": 1.0,
    },
    {
        "name": "Top 20 Más Populares (precio entre $0.01 y $0.1)",
        "method": "get_popular_by_price_range",
        "limit": 20,
        "min_price": 0.01,
        "max_price": 0.1,
    },
    {
        "name": "Top 20 Más Populares (precio entre $0.001 y $0.01)",
        "method": "get_popular_by_price_range",
        "limit": 20,
        "min_price": 0.001,
        "max_price": 0.01,
    },
    {
        "name": "Top 20 Más Populares (precio entre $0.0001 y $0.001)",
        "method": "get_popular_by_price_range",
        "limit": 20,
        "min_price": 0.0001,
        "max_price": 0.001,
    },
]