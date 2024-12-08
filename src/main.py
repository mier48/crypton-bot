# src/app/main.py

from app.trade_manager import TradeManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

def main():
    trade_manager = TradeManager()
    
    # Ejecutar el ciclo principal
    trade_manager.run()

if __name__ == "__main__":
    main()
