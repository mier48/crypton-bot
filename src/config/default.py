from typing import Dict

DEFAULT_PROFIT_MARGIN = 1.5 # 3% profit margin
DEFAULT_SLEEP_INTERVAL = 90 # 90 seconds wait interval
DEFAULT_INVESTMENT_AMOUNT = 25 # $25 investment per trade
DEFAULT_MAX_BUY_PRICE = 5 # $5 maximum unit purchase price
DEFAULT_LOT_SIZE_FILTER = "LOT_SIZE" # Lot size filter
DEFAULT_VALIDATION_MIN_SCORE = 5 # Minimum validation score
DEFAULT_STOP_LOSS_MARGIN = 15 # 25% stop loss margin
DEFAULT_CHECK_PRICE_INTERVAL = "5m" # 5-minute price interval for Binance API
DEFAULT_HISTORICAL_RANGE_HOURS = 5 * 24 # 7-day historical price range for Binance API
DEFAULT_USE_OPEN_AI_API = False # Do not use OpenAI API by default

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
        "name": "Top 20 Most Popular (price between $2.5 and $5)",
        "method": "get_popular_by_price_range",
        "limit": 40,
        "min_price": 2.5,
        "max_price": 5,
    },
    {
        "name": "Top 20 Most Popular (price between $1 and $2.5)",
        "method": "get_popular_by_price_range",
        "limit": 30,
        "min_price": 1,
        "max_price": 2.5,
    },
    {
        "name": "Top 20 Most Popular (price between $0.1 and $1.0)",
        "method": "get_popular_by_price_range",
        "limit": 20,
        "min_price": 0.1,
        "max_price": 1.0,
    },
    {
        "name": "Top 20 Most Popular (price between $0.01 and $0.1)",
        "method": "get_popular_by_price_range",
        "limit": 20,
        "min_price": 0.01,
        "max_price": 0.1,
    },
    {
        "name": "Top 20 Most Popular (price between $0.001 and $0.01)",
        "method": "get_popular_by_price_range",
        "limit": 20,
        "min_price": 0.001,
        "max_price": 0.01,
    },
    {
        "name": "Top 20 Most Popular (price between $0.0001 and $0.001)",
        "method": "get_popular_by_price_range",
        "limit": 20,
        "min_price": 0.0001,
        "max_price": 0.001,
    },
]
