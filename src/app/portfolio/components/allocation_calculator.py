from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from src.app.portfolio.models.portfolio_state import PortfolioState
from src.app.services.portfolio_optimizer import PortfolioOptimizer
from loguru import logger

class AllocationCalculator:
    """
    Componente responsable de calcular la asignación óptima para el portafolio
    y determinar si se necesita rebalancear.
    """
    
    def __init__(self, 
                 risk_aversion: float = 2.0, 
                 min_allocation: float = 0.01, 
                 max_allocation: float = 0.25,
                 rebalance_threshold: float = 0.15):
        """
        Inicializa el calculador de asignación óptima.
        
        Args:
            risk_aversion: Nivel de aversión al riesgo (2.0 = equilibrado)
            min_allocation: Porcentaje mínimo de asignación por activo
            max_allocation: Porcentaje máximo de asignación por activo
            rebalance_threshold: Umbral de desviación para rebalanceo
        """
        self.risk_aversion = risk_aversion
        self.min_allocation = min_allocation
        self.max_allocation = max_allocation
        self.rebalance_threshold = rebalance_threshold
        
        # Instanciar el optimizador de portafolio
        self.optimizer = PortfolioOptimizer(
            risk_aversion=self.risk_aversion,
            min_allocation=self.min_allocation,
            max_allocation=self.max_allocation
        )
    
    def calculate_optimal_allocation(self, state: PortfolioState, force_conservative: bool = False) -> Dict[str, float]:
        """
        Calcula la asignación óptima para el portafolio basándose en los datos de mercado.
        
        Args:
            state: Estado del portafolio con datos de mercado
            force_conservative: Si es True, calcula una asignación más conservadora
            
        Returns:
            Dict[str, float]: Asignación óptima como {símbolo: porcentaje}
        """
        try:
            # Verificar si tenemos datos
            if not state.market_data or not state.valid_symbols:
                logger.warning("Sin datos suficientes para optimización")
                return self._get_default_allocation(state.current_assets)
                
            # Ajustar aversión al riesgo según condiciones del mercado
            risk_aversion = self.risk_aversion
            if force_conservative or state.market_condition == "bearish":
                # Mayor aversión al riesgo en mercados bajistas
                risk_aversion = self.risk_aversion * 1.5
                logger.debug(f"Usando aversión al riesgo elevada: {risk_aversion} (mercado: {state.market_condition})")
            elif state.market_condition == "bullish" and state.market_volatility < 0.7:
                # Menor aversión al riesgo en mercados alcistas con volatilidad controlada
                risk_aversion = self.risk_aversion * 0.8
                logger.debug(f"Usando aversión al riesgo reducida: {risk_aversion} (mercado: {state.market_condition})")
                
            # Actualizar la aversión al riesgo del optimizador
            self.optimizer.risk_aversion = risk_aversion
            
            # Preparar datos para la optimización
            data = {}
            for symbol in state.valid_symbols:
                if symbol in state.market_data:
                    data[symbol] = state.market_data[symbol]
            
            # Calcular asignación óptima
            optimal_weights = self.optimizer.calculate_optimal_allocation(
                price_data=data,
                symbols=state.valid_symbols
            )
            
            # Verificar resultado de la optimización
            if optimal_weights is None or len(optimal_weights) == 0:
                logger.warning("La optimización no produjo resultados válidos")
                return self._get_default_allocation(state.current_assets)
                
            # Verificar si optimal_weights es un diccionario o una lista
            allocation = {}
            
            # Si es un diccionario (formato {su00edmbolo: peso})
            if isinstance(optimal_weights, dict):
                logger.debug(f"Procesando optimal_weights como diccionario con {len(optimal_weights)} elementos")
                
                # Crear una copia para evitar modificar durante la iteraciu00f3n
                weights_copy = dict(optimal_weights)
                
                for symbol, weight in weights_copy.items():
                    try:
                        # Primero verificar si es None
                        if weight is None:
                            allocation[symbol] = 0.0
                            continue
                            
                        # Intentar convertir a float si no lo es ya
                        if not isinstance(weight, (float, int, np.number)):
                            try:
                                weight = float(weight)
                            except (ValueError, TypeError):
                                logger.warning(f"No se pudo convertir el peso para {symbol} a float, valor: {weight}")
                                allocation[symbol] = 0.0
                                continue
                        
                        # Verificar si es NaN, inf o negativo
                        if np.isnan(weight) or np.isinf(weight) or weight < 0:
                            allocation[symbol] = 0.0
                        else:
                            # Asegurar que es float nativo de Python
                            allocation[symbol] = float(weight)
                    except Exception as e:
                        logger.warning(f"Error al procesar peso para {symbol}: {e}, estableciendo a 0.0")
                        allocation[symbol] = 0.0
                        
                # Asegurar que todos los su00edmbolos tengan un valor
                for symbol in state.valid_symbols:
                    if symbol not in allocation:
                        allocation[symbol] = 0.0
            
            # Si es una lista (formato [peso1, peso2, ...])
            else:
                logger.debug(f"Procesando optimal_weights como lista/array con {len(optimal_weights)} elementos")
                for i, symbol in enumerate(state.valid_symbols):
                    if i < len(optimal_weights):
                        try:
                            weight = optimal_weights[i]
                            
                            # Primero verificar si es None
                            if weight is None:
                                allocation[symbol] = 0.0
                                continue
                                
                            # Intentar convertir a float si no lo es ya
                            if not isinstance(weight, (float, int, np.number)):
                                try:
                                    weight = float(weight)
                                except (ValueError, TypeError):
                                    logger.warning(f"No se pudo convertir el peso {i} a float, valor: {weight}")
                                    allocation[symbol] = 0.0
                                    continue
                            
                            # Verificar si es NaN, inf o negativo
                            if np.isnan(weight) or np.isinf(weight) or weight < 0:
                                allocation[symbol] = 0.0
                            else:
                                # Asegurar que es float nativo de Python
                                allocation[symbol] = float(weight)
                        except Exception as e:
                            logger.warning(f"Error al procesar peso {i} para {symbol}: {e}, estableciendo a 0.0")
                            allocation[symbol] = 0.0
                    
            # Limpiar cualquier valor inválido que pudiera haber pasado
            for symbol in list(allocation.keys()):
                if np.isnan(allocation[symbol]) or np.isinf(allocation[symbol]) or allocation[symbol] < 0:
                    allocation[symbol] = 0.0
                    
            # Reservar un porcentaje para USDC como reserva de efectivo
            cash_reserve = 0.05  # 5% en USDC como reserva
            for symbol in allocation:
                allocation[symbol] *= (1 - cash_reserve)
            allocation['USDC'] = cash_reserve
            
            # Normalizar los pesos para que sumen 1
            total_weight = sum(allocation.values())
            if total_weight > 0:
                for symbol in allocation:
                    allocation[symbol] /= total_weight
            
            logger.info(f"Asignación óptima calculada para {len(allocation)} activos")
            return allocation
            
        except Exception as e:
            error_msg = str(e)
            # Si el error es vacío o solo contiene 0, proporcionar un mensaje más descriptivo
            if not error_msg or error_msg == '0':
                error_msg = 'Error en la optimización de portafolio - posibles valores no válidos o datos insuficientes'
                
            logger.error(f"Error calculando asignación óptima: {error_msg}")
            # Capturar más detalles de la excepción para diagnóstico
            import traceback
            logger.debug(f"Detalles de error en optimización: {traceback.format_exc()}")
            logger.info("Usando asignación por defecto como alternativa")
            return self._get_default_allocation(state.current_assets)
    
    def _get_default_allocation(self, assets: Dict[str, Dict]) -> Dict[str, float]:
        """
        Obtiene una asignación predeterminada cuando no se puede calcular la óptima.
        
        Args:
            assets: Diccionario de activos actuales
            
        Returns:
            Dict[str, float]: Asignación predeterminada
        """
        # Asignación predeterminada basada en la capitalización de mercado genuérica
        default_allocation = {
            'BTC': 0.35,    # 35% Bitcoin
            'ETH': 0.25,    # 25% Ethereum
            'BNB': 0.10,    # 10% Binance Coin
            'SOL': 0.05,    # 5% Solana
            'USDC': 0.25    # 25% USDC (reserva de efectivo)
        }
        
        # Adaptar a activos actuales si es posible
        if assets:
            # Obtener los activos actuales ordenados por valor
            sorted_assets = sorted(
                [(k, v) for k, v in assets.items()],
                key=lambda x: x[1]['value_usdc'],
                reverse=True
            )
            
            # Si hay activos con valor, usar un enfoque proporcional al valor
            if sorted_assets:
                allocation = {}
                total_value = sum([asset[1]['value_usdc'] for asset in sorted_assets])
                
                # Limitar a los 10 activos principales y mantener 25% en USDC
                top_assets = sorted_assets[:10]
                asset_allocation = 0.75  # 75% en activos
                
                # Calcular asignación proporcional al valor actual
                for symbol, asset_data in top_assets:
                    if total_value > 0:
                        weight = (asset_data['value_usdc'] / total_value) * asset_allocation
                        allocation[symbol] = weight
                
                # Añadir USDC
                allocation['USDC'] = 0.25
                
                # Normalizar
                total_weight = sum(allocation.values())
                if total_weight > 0:
                    for symbol in allocation:
                        allocation[symbol] /= total_weight
                        
                return allocation
        
        return default_allocation
    
    def check_significant_deviation(self, state: PortfolioState) -> bool:
        """
        Verifica si hay una desviación significativa entre la asignación actual y la objetivo.
        
        Args:
            state: Estado del portafolio con asignaciones actuales y objetivo
            
        Returns:
            bool: True si hay desviación significativa, False en caso contrario
        """
        if not state.current_allocation or not state.target_allocation:
            return False
            
        max_deviation = 0.0
        for symbol, target in state.target_allocation.items():
            current = state.current_allocation.get(symbol, 0.0)
            deviation = abs(current - target)
            max_deviation = max(max_deviation, deviation)
        
        logger.info(f"Desviación máxima: {max_deviation:.2f}, dentro del umbral aceptable" 
                    if max_deviation <= self.rebalance_threshold else 
                    f"Desviación máxima: {max_deviation:.2f}, excede el umbral")
        
        return max_deviation > self.rebalance_threshold
