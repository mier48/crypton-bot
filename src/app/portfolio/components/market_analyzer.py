from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from src.app.portfolio.models.portfolio_state import PortfolioState
from loguru import logger

class MarketAnalyzer:
    """
    Componente responsable de analizar las condiciones del mercado y determinar
    la estrategia u00f3ptima para el portafolio.
    """
    
    def __init__(self, reference_symbols: List[str] = None):
        """
        Inicializa el analizador de mercado.
        
        Args:
            reference_symbols: Su00edmbolos de referencia para analizar el mercado (default: BTC y ETH)
        """
        self.reference_symbols = reference_symbols or ['BTC', 'ETH']
        
    def analyze_market_condition(self, state: PortfolioState) -> Tuple[str, float]:
        """
        Analiza la condición actual del mercado basado en activos de referencia.
        
        Args:
            state: Estado del portafolio con datos de mercado
            
        Returns:
            Tuple[str, float]: Condición de mercado y nivel de volatilidad (0-1)
        """
        # Por defecto, condición neutral y volatilidad media
        market_condition = "neutral"
        market_volatility = 0.5
        
        try:
            # Verificar si tenemos datos para al menos un su00edmbolo de referencia
            reference_data = {}
            for symbol in self.reference_symbols:
                if symbol in state.market_data:
                    reference_data[symbol] = state.market_data[symbol]
            
            if not reference_data:
                logger.warning("No hay datos de referencia para analizar el mercado")
                return market_condition, market_volatility
            
            # Calcular tendencia y volatilidad para cada su00edmbolo de referencia
            trends = []
            volatilities = []
            
            for symbol, df in reference_data.items():
                if len(df) < 5:  # Necesitamos al menos 5 du00edas de datos
                    continue
                    
                # Calcular retornos diarios
                returns = df['close'].pct_change().dropna()
                
                # Calcular volatilidad (desviaciu00f3n estu00e1ndar de retornos)
                volatility = returns.std()
                volatilities.append(volatility)
                
                # Calcular tendencia (promedio de retornos recientes)
                trend = returns.tail(5).mean()  # Tendencia de los u00faltimos 5 du00edas
                trends.append(trend)
            
            # Promediar resultados
            if trends and volatilities:
                avg_trend = np.mean(trends)
                avg_volatility = np.mean(volatilities)
                
                # Determinar condición de mercado basado en tendencia
                if avg_trend > 0.01:  # Tendencia alcista significativa
                    market_condition = "bullish"
                elif avg_trend < -0.01:  # Tendencia bajista significativa
                    market_condition = "bearish"
                else:
                    market_condition = "neutral"
                
                # Normalizar volatilidad a un rango 0-1
                # Asumimos que 0.03 (3%) es volatilidad alta, 0.01 (1%) es baja
                market_volatility = min(1.0, max(0.0, (avg_volatility - 0.01) / 0.02))
                
            logger.debug(f"Condición de mercado: {market_condition}, Volatilidad: {market_volatility:.2f}")
            
        except Exception as e:
            logger.error(f"Error analizando condición de mercado: {e}")
        
        return market_condition, market_volatility
        
    def calculate_risk_metrics(self, state: PortfolioState) -> Dict[str, float]:
        """
        Calcula las métricas de riesgo para el portafolio actual.
        
        Args:
            state: Estado del portafolio con datos de mercado y asignaciones
            
        Returns:
            Dict[str, float]: Métricas de riesgo (retorno anual, volatilidad, ratio de Sharpe, etc.)
        """
        risk_metrics = {
            'annual_return': 0.0,
            'annual_volatility': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0
        }
        
        try:
            # Verificar si tenemos datos y asignación objetivo
            if not state.market_data or not state.target_allocation:
                return risk_metrics
                
            # Obtener retornos diarios para cada activo
            returns_data = {}
            for symbol, allocation in state.target_allocation.items():
                if symbol in state.market_data and allocation > 0.01:  # Solo activos con asignación significativa
                    df = state.market_data[symbol]
                    if len(df) > 5:  # Necesitamos suficientes datos
                        returns = df['close'].pct_change().dropna()
                        returns_data[symbol] = returns
            
            if not returns_data:
                return risk_metrics
                
            # Crear DataFrame conjunto de retornos
            returns_df = pd.DataFrame(returns_data)
            
            # Calcular retornos del portafolio usando la asignaciu00f3n objetivo
            weights = {}
            for symbol in returns_df.columns:
                weights[symbol] = state.target_allocation.get(symbol, 0.0)
                
            # Normalizar pesos
            total_weight = sum(weights.values())
            if total_weight > 0:
                for symbol in weights:
                    weights[symbol] /= total_weight
            
            # Calcular retornos del portafolio
            portfolio_returns = np.zeros(len(returns_df))
            for symbol, weight in weights.items():
                if symbol in returns_df.columns:
                    portfolio_returns += returns_df[symbol].values * weight
            
            # Calcular métricas de riesgo
            # Retorno anual (aproximado: 252 duodas de trading)
            annual_return = portfolio_returns.mean() * 252
            
            # Volatilidad anual
            annual_volatility = portfolio_returns.std() * np.sqrt(252)
            
            # Ratio de Sharpe (asumiendo tasa libre de riesgo = 0.02 o 2%)
            risk_free_rate = 0.02  # 2% anual
            sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility if annual_volatility > 0 else 0
            
            # Calcular drawdown máximo
            portfolio_value = (1 + portfolio_returns).cumprod()
            rolling_max = np.maximum.accumulate(portfolio_value)
            drawdowns = (portfolio_value - rolling_max) / rolling_max
            max_drawdown = abs(drawdowns.min()) if len(drawdowns) > 0 else 0
            
            # Actualizar métricas
            risk_metrics['annual_return'] = float(annual_return)
            risk_metrics['annual_volatility'] = float(annual_volatility)
            risk_metrics['sharpe_ratio'] = float(sharpe_ratio)
            risk_metrics['max_drawdown'] = float(max_drawdown)
            
            logger.debug(f"Métricas de riesgo calculadas: {risk_metrics}")
            
        except Exception as e:
            logger.error(f"Error calculando métricas de riesgo: {e}")
        
        return risk_metrics
