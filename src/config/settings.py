from pydantic import BaseSettings, Field
from config.default import DEFAULT_CHECK_PRICE_INTERVAL, DEFAULT_HISTORICAL_RANGE_HOURS, DEFAULT_EXT_HISTORICAL_MULTIPLIER, DEFAULT_MAX_EXPOSURE_PERCENT, DEFAULT_RISK_PER_TRADE_PERCENT
from datetime import datetime, timezone
from typing import Dict, Any

class Settings(BaseSettings):
    MAX_RECORDS: int = Field(500, env="MAX_RECORDS")
    PROFIT_MARGIN: float = Field(3.0, env="PROFIT_MARGIN")  # Ajustado al default 3%
    STOP_LOSS_MARGIN: float = Field(15.0, env="STOP_LOSS_MARGIN")  # 15%
    SLEEP_INTERVAL: int = Field(90, env="SLEEP_INTERVAL")
    INVESTMENT_AMOUNT: float = Field(15.0, env="INVESTMENT_AMOUNT")  # Fijo a $15 según usuario
    MAX_BUY_PRICE: float = Field(5.0, env="MAX_BUY_PRICE")  # Fijo a $5 según usuario
    MAX_WORKERS: int = Field(10, env="MAX_WORKERS")
    MIN_TRADE_USD: float = Field(5.0, env="MIN_TRADE_USD")
    USE_OPEN_AI_API: bool = Field(False, env="USE_OPEN_AI_API")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    METRICS_PORT: int = Field(8000, env="METRICS_PORT")
    # Interval settings
    DEFAULT_CHECK_PRICE_INTERVAL: str = Field(DEFAULT_CHECK_PRICE_INTERVAL, env="DEFAULT_CHECK_PRICE_INTERVAL")
    DEFAULT_HISTORICAL_RANGE_HOURS: int = Field(DEFAULT_HISTORICAL_RANGE_HOURS, env="DEFAULT_HISTORICAL_RANGE_HOURS")
    DEFAULT_EXT_HISTORICAL_MULTIPLIER: int = Field(DEFAULT_EXT_HISTORICAL_MULTIPLIER, env="DEFAULT_EXT_HISTORICAL_MULTIPLIER")
    OPTUNA_PARAM_SPACE: Dict[str, Any] = Field(
        { 'sma_period': (5, 50), 'rsi_threshold': (20, 80) }, env=None
    )
    OPTUNA_TRIALS: int = Field(50, env="OPTUNA_TRIALS")
    BACKTEST_START: datetime = Field(datetime(2025, 1, 1, tzinfo=timezone.utc), env=None)
    BACKTEST_END: datetime   = Field(datetime(2025, 4, 1, tzinfo=timezone.utc), env=None)
    OVERFITTING_THRESHOLD: float = Field(0.1, env="OVERFITTING_THRESHOLD")
    # Risk limits
    MAX_EXPOSURE_PERCENT: float = Field(DEFAULT_MAX_EXPOSURE_PERCENT, env="MAX_EXPOSURE_PERCENT")
    RISK_PER_TRADE_PERCENT: float = Field(DEFAULT_RISK_PER_TRADE_PERCENT, env="RISK_PER_TRADE_PERCENT")
    ANOMALY_CONTAMINATION: float = Field(0.01, env="ANOMALY_CONTAMINATION")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()
