from pydantic import BaseSettings, Field
from config.default import DEFAULT_CHECK_PRICE_INTERVAL, DEFAULT_HISTORICAL_RANGE_HOURS, DEFAULT_EXT_HISTORICAL_MULTIPLIER, DEFAULT_MAX_EXPOSURE_PERCENT, DEFAULT_RISK_PER_TRADE_PERCENT
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

class Settings(BaseSettings):
    MAX_RECORDS: int = Field(500, env="MAX_RECORDS")
    PROFIT_MARGIN: float = Field(3.0, env="PROFIT_MARGIN")  # Ajustado al default 2%
    STOP_LOSS_MARGIN: float = Field(15.0, env="STOP_LOSS_MARGIN")  # 15%
    SLEEP_INTERVAL: int = Field(120, env="SLEEP_INTERVAL")
    INVESTMENT_AMOUNT: float = Field(20.0, env="INVESTMENT_AMOUNT")  # Fijo a $20 según usuario
    MAX_BUY_PRICE: float = Field(5.0, env="MAX_BUY_PRICE")  # Fijo a $5 según usuario
    MAX_WORKERS: int = Field(10, env="MAX_WORKERS")
    MIN_TRADE_USD: float = Field(5.0, env="MIN_TRADE_USD")
    USE_OPEN_AI_API: bool = Field(False, env="USE_OPEN_AI_API")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    METRICS_PORT: int = Field(8000, env="METRICS_PORT")
    
    # Configuración del sistema de optimización de portafolio
    EXECUTION_MODE: str = Field("trade", env="EXECUTION_MODE")  # Opciones: 'trade', 'portfolio', 'full'
    RISK_AVERSION: float = Field(0.6, env="RISK_AVERSION")  # 0 (solo retorno) a 1 (solo riesgo)
    MAX_ALLOCATION_PER_ASSET: float = Field(0.25, env="MAX_ALLOCATION_PER_ASSET")  # Máximo 25% en un solo activo
    REBALANCE_THRESHOLD: float = Field(0.15, env="REBALANCE_THRESHOLD")  # Rebalancear cuando desviación > 15%
    SCHEDULED_REBALANCE_HOURS: int = Field(24, env="SCHEDULED_REBALANCE_HOURS")  # Rebalanceo diario
    PORTFOLIO_CHECK_INTERVAL: int = Field(3600, env="PORTFOLIO_CHECK_INTERVAL")  # Verificar cada hora
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
    
    # Configuración del sistema de adaptación a ciclos de mercado
    ENABLE_MARKET_CYCLE_ADAPTATION: bool = Field(True, env="ENABLE_MARKET_CYCLE_ADAPTATION")
    MARKET_CYCLE_UPDATE_INTERVAL: int = Field(8, env="MARKET_CYCLE_UPDATE_INTERVAL")  # Horas
    MARKET_CYCLE_LOOKBACK_DAYS: int = Field(90, env="MARKET_CYCLE_LOOKBACK_DAYS")
    
    # Configuraciones para diferentes ciclos de mercado (usado como valores base)
    ACCUMULATION_RISK_AVERSION: float = Field(0.5, env="ACCUMULATION_RISK_AVERSION")
    UPTREND_RISK_AVERSION: float = Field(0.3, env="UPTREND_RISK_AVERSION")
    DISTRIBUTION_RISK_AVERSION: float = Field(0.7, env="DISTRIBUTION_RISK_AVERSION")
    DOWNTREND_RISK_AVERSION: float = Field(0.9, env="DOWNTREND_RISK_AVERSION")
    
    # Configuración DCA (Dollar Cost Averaging)
    ENABLE_DCA: bool = Field(True, env="ENABLE_DCA")
    DCA_MAX_BUYS: int = Field(3, env="DCA_MAX_BUYS")  # Máximo número de compras DCA
    DCA_PRICE_DECREASE: float = Field(0.15, env="DCA_PRICE_DECREASE")  # % de caída para activar DCA
    
    # Configuración de notificaciones de ciclos de mercado
    NOTIFY_MARKET_CYCLE_CHANGES: bool = Field(True, env="NOTIFY_MARKET_CYCLE_CHANGES")  # Enviar notificación al cambiar de ciclo
    NOTIFY_ADAPTATION_DETAILS: bool = Field(False, env="NOTIFY_ADAPTATION_DETAILS")  # Enviar detalles de adaptaciones

    EXECUTE_BUYS: bool = Field(False, env="EXECUTE_BUYS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()
