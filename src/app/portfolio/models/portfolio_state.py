from typing import Dict, List, Optional, Any
import pandas as pd
from loguru import logger

class PortfolioState:
    """
    Clase que representa el estado actual del portafolio.
    Contiene la información sobre los activos, su asignación actual y objetivo,
    métricas de riesgo y condiciones de mercado.
    """
    
    def __init__(self):
        # Balances y asignaciones
        self.current_assets: Dict[str, Dict[str, Any]] = {}
        self.target_allocation: Dict[str, float] = {}
        self.current_allocation: Dict[str, float] = {}
        
        # Valor total del portafolio
        self.total_value: float = 0.0
        self.usdc_balance: float = 0.0
        
        # Datos de mercado
        self.market_data: Dict[str, pd.DataFrame] = {}
        self.valid_symbols: List[str] = []
        
        # Métricas de riesgo
        self.risk_metrics: Dict[str, float] = {
            'annual_return': 0.0,
            'annual_volatility': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0
        }
        
        # Condiciones de mercado
        self.market_condition: str = "neutral"
        self.market_volatility: float = 0.0
        
        # Historial de rebalanceos
        self.last_rebalance_time: Optional[int] = None
        self.rebalance_history: List[Dict[str, Any]] = []
    
    def clear_market_data(self):
        """
        Limpia los datos de mercado para liberar memoria.
        """
        self.market_data = {}
    
    def needs_rebalance(self, threshold: float) -> bool:
        """
        Determina si el portafolio necesita ser rebalanceado basado en la desviación 
        de la asignación actual respecto a la objetivo.
        
        Args:
            threshold: Umbral de desviación para considerar necesario el rebalanceo
            
        Returns:
            bool: True si se necesita rebalanceo, False en caso contrario
        """
        if not self.target_allocation or not self.current_allocation:
            return False
            
        max_deviation = 0.0
        for symbol, target in self.target_allocation.items():
            current = self.current_allocation.get(symbol, 0.0)
            deviation = abs(current - target)
            max_deviation = max(max_deviation, deviation)
            
        return max_deviation > threshold
