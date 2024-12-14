# src/main.py

from app.managers.trade_manager import TradeManager
from config.default import (
    DEFAULT_PROFIT_MARGIN,
    DEFAULT_SLEEP_INTERVAL,
    DEFAULT_INVESTMENT_AMOUNT,
    DEFAULT_STOP_LOSS_MARGIN
)

def main():
    trade_manager = TradeManager(
        max_records=500,
        profit_margin=DEFAULT_PROFIT_MARGIN,
        stop_loss_margin=DEFAULT_STOP_LOSS_MARGIN,
        sleep_interval=DEFAULT_SLEEP_INTERVAL,
        investment_amount=DEFAULT_INVESTMENT_AMOUNT,
        max_workers=10
    )
    trade_manager.run()

if __name__ == "__main__":
    main()
