from pydantic import BaseSettings, Field
from config.default import DEFAULT_CHECK_PRICE_INTERVAL, DEFAULT_HISTORICAL_RANGE_HOURS

class Settings(BaseSettings):
    MAX_RECORDS: int = Field(500, env="MAX_RECORDS")
    PROFIT_MARGIN: float = Field(1.5, env="PROFIT_MARGIN")
    STOP_LOSS_MARGIN: float = Field(15.0, env="STOP_LOSS_MARGIN")
    SLEEP_INTERVAL: int = Field(90, env="SLEEP_INTERVAL")
    INVESTMENT_AMOUNT: float = Field(25.0, env="INVESTMENT_AMOUNT")
    MAX_BUY_PRICE: float = Field(5.0, env="MAX_BUY_PRICE")
    MAX_WORKERS: int = Field(10, env="MAX_WORKERS")
    MIN_TRADE_USD: float = Field(5.0, env="MIN_TRADE_USD")
    USE_OPEN_AI_API: bool = Field(False, env="USE_OPEN_AI_API")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    METRICS_PORT: int = Field(8000, env="METRICS_PORT")
    # Interval settings
    DEFAULT_CHECK_PRICE_INTERVAL: str = Field(DEFAULT_CHECK_PRICE_INTERVAL, env="DEFAULT_CHECK_PRICE_INTERVAL")
    DEFAULT_HISTORICAL_RANGE_HOURS: int = Field(DEFAULT_HISTORICAL_RANGE_HOURS, env="DEFAULT_HISTORICAL_RANGE_HOURS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()
