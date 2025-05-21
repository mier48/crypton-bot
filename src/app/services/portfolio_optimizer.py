import numpy as np
from typing import Dict, List, Tuple, Optional
from loguru import logger
import pandas as pd
from scipy.optimize import minimize

class PortfolioOptimizer:
    """
    Optimiza la asignación de capital entre activos utilizando técnicas modernas de
    gestión de portafolio, considerando volatilidad, correlación y expectativas de retorno.
    
    Implementa:
    - Optimización de Markowitz (frontera eficiente)
    - Ajuste dinámico por condiciones de mercado
    - Límites inteligentes de exposición por activo y grupos correlacionados
    - Control de riesgo de cola (tail risk)
    """
    
    def __init__(
        self, 
        min_allocation: float = 0.01,  # Mínima asignación por activo
        max_allocation: float = 0.25,  # Máxima asignación por activo
        max_correlation_exposure: float = 0.40,  # Máxima exposición a activos altamente correlacionados
        risk_aversion: float = 0.5,  # 0 (solo rendimiento) a 1 (solo riesgo)
        rebalance_threshold: float = 0.15,  # Desviación que activa rebalanceo
        correlation_threshold: float = 0.7  # Umbral para considerar alta correlación
    ):
        self.min_allocation = min_allocation
        self.max_allocation = max_allocation
        self.max_correlation_exposure = max_correlation_exposure
        self.risk_aversion = risk_aversion
        self.rebalance_threshold = rebalance_threshold
        self.correlation_threshold = correlation_threshold
        
    def calculate_optimal_allocation(self, 
                                    symbols: List[str],
                                    price_data: Dict[str, pd.DataFrame],
                                    current_holdings: Optional[Dict[str, float]] = None,
                                    market_condition: str = 'neutral') -> Dict[str, float]:
        """
        Calcula la asignación óptima de capital entre múltiples activos.
        
        Args:
            symbols: Lista de símbolos a considerar
            price_data: Datos históricos de precios por símbolo
            current_holdings: Tenencias actuales {símbolo: valor_en_usdc}
            market_condition: Condición actual del mercado ('bullish', 'neutral', 'bearish')
            
        Returns:
            Diccionario {símbolo: porcentaje_asignado}
        """
        try:
            # 1. Calcular retornos y estadísticas
            returns_data = {}
            for symbol in symbols:
                if symbol in price_data and len(price_data[symbol]) > 0:
                    # Calcular returns diarios
                    closes = price_data[symbol]['close']
                    returns_data[symbol] = closes.pct_change().dropna()
            
            # Crear matriz de retornos
            returns_df = pd.DataFrame(returns_data)
            
            # 2. Calcular matriz de covarianza y retornos esperados
            # Verificar que haya suficientes datos para el análisis
            if returns_df.empty or len(returns_df.columns) < 2 or len(returns_df) < 5:
                logger.warning(f"Datos insuficientes para optimización: {len(returns_df.columns)} símbolos, {len(returns_df)} días")
                # Devolver una asignación uniforme simple
                equal_weight = 1.0 / len(symbols) if symbols else 1.0
                return {symbol: equal_weight for symbol in symbols}
                
            cov_matrix = returns_df.cov() * 365  # Anualizada
            exp_returns = returns_df.mean() * 365  # Retornos anualizados
            
            # 3. Ajustar retornos esperados según condición de mercado
            if market_condition == 'bullish':
                exp_returns = exp_returns * 1.2  # Incrementar expectativas en mercado alcista
            elif market_condition == 'bearish':
                exp_returns = exp_returns * 0.8  # Reducir expectativas en mercado bajista
                
            # 4. Identificar grupos de activos correlacionados
            corr_matrix = returns_df.corr()
            correlation_groups = self._identify_correlation_groups(corr_matrix)
            
            # 5. Optimizar portafolio
            weights = self._optimize_portfolio(exp_returns, cov_matrix, correlation_groups)
            
            # 6. Construir asignación recomendada
            allocation = {symbol: weights[i] for i, symbol in enumerate(returns_df.columns)}
            
            # 7. Determinar si se requiere rebalanceo
            if current_holdings:
                total_current = sum(current_holdings.values())
                current_weights = {k: v/total_current for k, v in current_holdings.items()}
                rebalance_needed = self._check_rebalance_needed(allocation, current_weights)
                if not rebalance_needed:
                    logger.info("No se requiere rebalanceo, desviación dentro de umbral aceptable")
                    return current_weights
            
            logger.info(f"Asignación óptima calculada: {allocation}")
            return allocation
            
        except Exception as e:
            logger.error(f"Error calculando asignación óptima: {e}")
            # Retornar asignación uniforme en caso de error
            equal_weight = 1.0 / len(symbols)
            return {symbol: equal_weight for symbol in symbols}
    
    def _optimize_portfolio(self, 
                          expected_returns: pd.Series, 
                          cov_matrix: pd.DataFrame,
                          correlation_groups: List[List[str]]) -> np.ndarray:
        """
        Optimiza la asignación de pesos para encontrar el portafolio óptimo
        según criterio de Sharpe Ratio modificado.
        """
        n_assets = len(expected_returns)
        
        # Verificar que haya suficientes activos para optimizar
        if n_assets == 0:
            logger.warning("No hay activos para optimizar el portafolio")
            return np.array([])
            
        # Verificar que la matriz de covarianza no tenga NaN o infinitos
        if np.isnan(cov_matrix.values).any() or np.isinf(cov_matrix.values).any():
            logger.warning("Matriz de covarianza contiene valores NaN o infinitos")
            return np.array([1.0/n_assets] * n_assets)
            
        init_guess = np.array([1.0/n_assets] * n_assets)
        bounds = [(self.min_allocation, self.max_allocation)] * n_assets
        
        # Restricción: suma de pesos = 1
        constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}]
        
        # Restricciones adicionales para grupos correlacionados
        for group in correlation_groups:
            # Índices de activos en grupo correlacionado
            indices = [list(expected_returns.index).index(asset) for asset in group]
            constraints.append({
                'type': 'ineq',
                'fun': lambda x, idx=indices: self.max_correlation_exposure - np.sum(x[idx])
            })
        
        # Función a optimizar: rendimiento - riesgo ajustado
        def objective(weights):
            portfolio_return = np.sum(expected_returns * weights)
            # Manejar caso donde la matriz de covarianza puede dar resultado negativo debido a errores numéricos
            try:
                variance = np.dot(weights.T, np.dot(cov_matrix, weights))
                # Asegurarse que la varianza no sea negativa (lo que daría error al calcular la raíz)
                portfolio_risk = np.sqrt(max(0.0001, variance))
            except Exception as e:
                logger.warning(f"Error en cálculo de riesgo de portafolio: {e}")
                # Asignar un valor razonable para evitar errores
                portfolio_risk = 0.2  # 20% volatilidad como valor conservador
                
            # Evitar división por cero o valores muy pequeños
            if portfolio_risk < 0.0001:
                portfolio_risk = 0.0001
                
            # Risk-adjusted return (combinación de retorno y riesgo)
            return -(portfolio_return - (self.risk_aversion * portfolio_risk))
        
        # Optimizar
        result = minimize(objective, init_guess, method='SLSQP', bounds=bounds, constraints=constraints)
        
        if result.success:
            return result.x
        else:
            logger.warning(f"Optimización no convergió: {result.message}")
            return init_guess
    
    def _identify_correlation_groups(self, corr_matrix: pd.DataFrame) -> List[List[str]]:
        """
        Identifica grupos de activos altamente correlacionados entre sí.
        """
        correlation_groups = []
        processed = set()
        
        for asset in corr_matrix.columns:
            if asset in processed:
                continue
                
            # Encontrar activos correlacionados con este
            correlated = []
            for other in corr_matrix.columns:
                if other != asset and abs(corr_matrix.loc[asset, other]) > self.correlation_threshold:
                    correlated.append(other)
            
            if correlated:
                group = [asset] + correlated
                correlation_groups.append(group)
                processed.update(group)
            else:
                processed.add(asset)
        
        return correlation_groups
    
    def _check_rebalance_needed(self, 
                              target_allocation: Dict[str, float], 
                              current_allocation: Dict[str, float]) -> bool:
        """
        Determina si las diferencias entre asignación actual y objetivo 
        justifican un rebalanceo.
        """
        max_deviation = 0.0
        
        for symbol, target_weight in target_allocation.items():
            current_weight = current_allocation.get(symbol, 0.0)
            deviation = abs(current_weight - target_weight)
            max_deviation = max(max_deviation, deviation)
        
        return max_deviation > self.rebalance_threshold
    
    def calculate_risk_metrics(self, portfolio_weights: Dict[str, float], price_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """
        Calcula métricas de riesgo para el portafolio actual.
        """
        try:
            # Preparar datos de retornos
            returns_data = {}
            for symbol, df in price_data.items():
                if symbol in portfolio_weights and len(df) > 0:
                    returns_data[symbol] = df['close'].pct_change().dropna()
            
            returns_df = pd.DataFrame(returns_data)
            weights = np.array([portfolio_weights.get(col, 0) for col in returns_df.columns])
            
            # Calcular retornos del portafolio
            portfolio_returns = returns_df.dot(weights)
            
            # Calcular métricas
            annual_return = portfolio_returns.mean() * 365
            annual_volatility = portfolio_returns.std() * np.sqrt(365)
            sharpe_ratio = annual_return / annual_volatility if annual_volatility != 0 else 0
            max_drawdown = (portfolio_returns.cumsum() - portfolio_returns.cumsum().cummax()).min()
            var_95 = portfolio_returns.quantile(0.05)  # VaR al 95%
            cvar_95 = portfolio_returns[portfolio_returns <= var_95].mean()  # CVaR/Expected Shortfall
            
            return {
                'annual_return': float(annual_return),
                'annual_volatility': float(annual_volatility),
                'sharpe_ratio': float(sharpe_ratio),
                'max_drawdown': float(max_drawdown),
                'var_95': float(var_95),
                'cvar_95': float(cvar_95)
            }
            
        except Exception as e:
            logger.error(f"Error calculando métricas de riesgo: {e}")
            return {
                'annual_return': 0.0,
                'annual_volatility': 0.0,
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'var_95': 0.0,
                'cvar_95': 0.0
            }
    
    def adjust_for_market_regime(self, 
                               base_allocation: Dict[str, float],
                               market_volatility: float,
                               market_trend: str) -> Dict[str, float]:
        """
        Ajusta la asignación base según el régimen actual del mercado.
        
        Args:
            base_allocation: Asignación base optimizada
            market_volatility: Volatilidad actual normalizada (0-1)
            market_trend: Tendencia identificada ('strong_bullish', 'bullish', 'neutral', 'bearish', 'strong_bearish')
            
        Returns:
            Asignación ajustada al régimen de mercado
        """
        adjusted_allocation = base_allocation.copy()
        total_weight = sum(adjusted_allocation.values())
        
        # Factor de reducción basado en volatilidad (mayor volatilidad = mayor reducción)
        reduction_factor = 1.0 - (market_volatility * 0.5)  # 0.5 a 1.0
        
        # Factores de ajuste según tendencia
        if market_trend == 'strong_bearish':
            # Situación de riesgo extremo - reducir exposición significativamente
            adjusted_allocation = {k: v * 0.5 * reduction_factor for k, v in adjusted_allocation.items()}
        elif market_trend == 'bearish':
            # Mercado bajista - reducir exposición moderadamente
            adjusted_allocation = {k: v * 0.75 * reduction_factor for k, v in adjusted_allocation.items()}
        elif market_trend == 'neutral':
            # Mercado neutral - mantener exposición base con ajuste por volatilidad
            adjusted_allocation = {k: v * reduction_factor for k, v in adjusted_allocation.items()}
        # En mercados alcistas no se reduce la exposición
        
        # Normalizar para que sume 1.0
        adj_total = sum(adjusted_allocation.values())
        if adj_total > 0:
            adjusted_allocation = {k: v / adj_total for k, v in adjusted_allocation.items()}
        
        return adjusted_allocation
