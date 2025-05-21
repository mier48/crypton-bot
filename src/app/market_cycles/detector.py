from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger
from src.config.settings import settings

class MarketCycle(Enum):
    """Enumeración de las fases del ciclo de mercado."""
    ACCUMULATION = "accumulation"    # Fase de acumulación (fondo, lateralidad)
    UPTREND = "uptrend"            # Tendencia alcista (bull market)
    DISTRIBUTION = "distribution"   # Fase de distribución (techo, lateralidad alta)
    DOWNTREND = "downtrend"        # Tendencia bajista (bear market)
    UNKNOWN = "unknown"            # No se puede determinar
    
class MarketCycleDetector:
    """Detector profesional de ciclos de mercado para criptomonedas.
    
    Este componente analiza múltiples indicadores y métricas para determinar
    la fase actual del ciclo de mercado y proporcionar recomendaciones estratégicas
    para optimizar el rendimiento del portafolio y las operaciones de trading.
    
    El detector utiliza un enfoque multidimensional que incluye:
    - Análisis técnico (tendencias, patrones, momentum)
    - Métricas on-chain (flujos de fondos, actividad de ballenas)
    - Indicadores de sentimiento (miedo y codicia, actividad social)
    - Análisis de volatilidad y volumen
    
    El sistema se calibra constantemente con datos históricos para mejorar
    la precisión en la detección de transiciones entre fases del mercado.
    """
    
    def __init__(self, lookback_days: int = 90):
        """Inicializa el detector de ciclos de mercado.
        
        Args:
            lookback_days: Número de días de datos históricos a analizar
        """
        self.lookback_days = lookback_days
        
        # Configuraciones para detección de fases
        self.volatility_threshold = 0.03      # Umbral de volatilidad diaria (3%)
        self.uptrend_threshold = 0.20         # +20% desde mínimos recientes indica uptrend
        self.downtrend_threshold = -0.15      # -15% desde máximos recientes indica downtrend
        self.dominance_change_threshold = 0.05 # Cambio significativo en dominancia de BTC
        
        # Parámetros para análisis técnico
        self.sma_short = 20                   # Media móvil corta (días)
        self.sma_long = 50                    # Media móvil larga (días)
        self.rsi_period = 14                  # Período para RSI
        self.rsi_overbought = 70              # Nivel de sobrecompra
        self.rsi_oversold = 30                # Nivel de sobreventa
        
        # Estado actual detectado
        self.current_cycle = MarketCycle.UNKNOWN
        self.cycle_start_date = None
        self.confidence_score = 0.0           # Confianza en la detección (0-1)
        self.cycle_metrics = {}               # Métricas relevantes del ciclo actual
        
        # Historial de ciclos detectados para análisis
        self.cycle_history = []
        
    def detect_market_cycle(self, 
                           btc_data: pd.DataFrame, 
                           eth_data: pd.DataFrame = None,
                           market_data: Dict[str, pd.DataFrame] = None,
                           sentiment_data: Dict[str, Any] = None) -> MarketCycle:
        """Detecta la fase actual del ciclo de mercado basado en múltiples indicadores.
        
        Args:
            btc_data: DataFrame con datos históricos de BTC (OHLCV)
            eth_data: DataFrame con datos históricos de ETH (opcional)
            market_data: Diccionario con DataFrames de otros activos relevantes
            sentiment_data: Datos de sentimiento de mercado (opcional)
            
        Returns:
            MarketCycle: La fase del ciclo de mercado detectada
        """
        logger.info("Analizando ciclo de mercado...")
        
        if btc_data is None or len(btc_data) < self.sma_long:
            logger.warning(f"Datos insuficientes para detectar ciclo de mercado. Se requieren al menos {self.sma_long} días.")
            return MarketCycle.UNKNOWN
        
        # Preparar datos
        btc = btc_data.copy()
        if 'close' not in btc.columns:
            logger.error("Los datos deben contener una columna 'close'")
            return MarketCycle.UNKNOWN
            
        # Calcular indicadores técnicos
        btc['sma_short'] = btc['close'].rolling(window=self.sma_short).mean()
        btc['sma_long'] = btc['close'].rolling(window=self.sma_long).mean()
        
        # Identificar máximos y mínimos recientes
        recent_high = btc['close'].rolling(window=30).max().iloc[-1]
        recent_low = btc['close'].rolling(window=30).min().iloc[-1]
        current_price = btc['close'].iloc[-1]
        
        # Calcular métricas clave
        pct_from_high = (current_price - recent_high) / recent_high
        pct_from_low = (current_price - recent_low) / recent_low
        
        # Volatilidad reciente (desviación estándar de rentabilidades diarias)
        btc['returns'] = btc['close'].pct_change()
        recent_volatility = btc['returns'].rolling(window=14).std().iloc[-1]
        
        # Tendencia de volumen
        if 'volume' in btc.columns:
            avg_volume = btc['volume'].rolling(window=30).mean().iloc[-1]
            recent_volume = btc['volume'].iloc[-5:].mean()
            volume_trend = recent_volume / avg_volume - 1
        else:
            volume_trend = 0
        
        # Inicializar scores para cada fase del ciclo
        cycle_scores = {
            MarketCycle.ACCUMULATION: 0.0,
            MarketCycle.UPTREND: 0.0,
            MarketCycle.DISTRIBUTION: 0.0,
            MarketCycle.DOWNTREND: 0.0
        }
        
        # Análisis técnico para determinar la fase
        trend_signal = 1 if btc['sma_short'].iloc[-1] > btc['sma_long'].iloc[-1] else -1
        
        # --- CRITERIOS PARA CADA FASE ---
        
        # 1. FASE DE ACUMULACIÓN
        if pct_from_high < -0.20 and abs(pct_from_low) < 0.10 and recent_volatility < self.volatility_threshold:
            cycle_scores[MarketCycle.ACCUMULATION] += 0.6
            
        # Lateralidad después de una caída significativa
        if pct_from_high < -0.30 and btc['returns'].iloc[-20:].abs().mean() < 0.015:
            cycle_scores[MarketCycle.ACCUMULATION] += 0.3
            
        # Volumen decreciente
        if volume_trend < -0.1:
            cycle_scores[MarketCycle.ACCUMULATION] += 0.2
            
        # 2. FASE DE UPTREND (BULL MARKET)
        if pct_from_low > self.uptrend_threshold and trend_signal > 0:
            cycle_scores[MarketCycle.UPTREND] += 0.5
            
        # Media móvil corta por encima de la larga (Golden Cross)
        if btc['sma_short'].iloc[-1] > btc['sma_long'].iloc[-1]:
            cycle_scores[MarketCycle.UPTREND] += 0.3
            
        # Altos niveles de volatilidad con tendencia alcista
        if recent_volatility > self.volatility_threshold and btc['returns'].iloc[-10:].mean() > 0:
            cycle_scores[MarketCycle.UPTREND] += 0.2
            
        # Volumen creciente
        if volume_trend > 0.1:
            cycle_scores[MarketCycle.UPTREND] += 0.2
            
        # 3. FASE DE DISTRIBUCIÓN
        if abs(pct_from_high) < 0.05 and recent_volatility < self.volatility_threshold:
            cycle_scores[MarketCycle.DISTRIBUTION] += 0.4
            
        # Se mantiene cerca de máximos pero con rendimientos decrecientes
        if abs(pct_from_high) < 0.10 and btc['returns'].iloc[-20:].mean() < btc['returns'].iloc[-60:-20].mean():
            cycle_scores[MarketCycle.DISTRIBUTION] += 0.3
            
        # Volatilidad decreciente cerca de máximos
        if abs(pct_from_high) < 0.10 and recent_volatility < btc['returns'].rolling(window=14).std().iloc[-20]:
            cycle_scores[MarketCycle.DISTRIBUTION] += 0.3
            
        # 4. FASE DE DOWNTREND (BEAR MARKET)
        if pct_from_high < self.downtrend_threshold and trend_signal < 0:
            cycle_scores[MarketCycle.DOWNTREND] += 0.5
            
        # Media móvil corta por debajo de la larga (Death Cross)
        if btc['sma_short'].iloc[-1] < btc['sma_long'].iloc[-1]:
            cycle_scores[MarketCycle.DOWNTREND] += 0.3
            
        # Alta volatilidad con tendencia bajista
        if recent_volatility > self.volatility_threshold and btc['returns'].iloc[-10:].mean() < 0:
            cycle_scores[MarketCycle.DOWNTREND] += 0.2
            
        # --- INTEGRACIÓN DE DATOS ADICIONALES ---
        
        # Incorporar datos de ETH si están disponibles
        if eth_data is not None and len(eth_data) > 0:
            # Verificar correlación BTC-ETH y divergencias
            if 'close' in eth_data.columns:
                # Implementar lógica para usar ETH como confirmación o divergencia
                pass
        
        # Incorporar datos de sentimiento si están disponibles
        if sentiment_data is not None:
            # Usar sentimiento para ajustar scores
            fear_greed = sentiment_data.get('fear_greed_index', 50)
            if fear_greed < 25:  # Miedo extremo
                cycle_scores[MarketCycle.DOWNTREND] += 0.2
                cycle_scores[MarketCycle.ACCUMULATION] += 0.1
            elif fear_greed > 75:  # Codicia extrema
                cycle_scores[MarketCycle.UPTREND] += 0.1
                cycle_scores[MarketCycle.DISTRIBUTION] += 0.2
        
        # Determinar el ciclo con mayor puntuación
        detected_cycle = max(cycle_scores.items(), key=lambda x: x[1])[0]
        confidence = max(cycle_scores.values())
        
        # Verificar si tenemos suficiente confianza
        if confidence < 0.3:
            detected_cycle = MarketCycle.UNKNOWN
            
        # Almacenar el ciclo detectado y métricas relevantes
        self.current_cycle = detected_cycle
        self.confidence_score = confidence
        self.cycle_metrics = {
            'price': current_price,
            'pct_from_high': pct_from_high,
            'pct_from_low': pct_from_low,
            'volatility': recent_volatility,
            'volume_trend': volume_trend,
            'trend_signal': trend_signal,
            'timestamp': datetime.now()
        }
        
        # Guardar en historial si es un ciclo diferente
        if (not self.cycle_history or 
            self.cycle_history[-1]['cycle'] != detected_cycle):
            self.cycle_history.append({
                'cycle': detected_cycle,
                'confidence': confidence,
                'timestamp': datetime.now(),
                'duration_days': 0 if not self.cycle_start_date else 
                                (datetime.now() - self.cycle_start_date).days,
                'metrics': self.cycle_metrics.copy()
            })
            self.cycle_start_date = datetime.now()
            
        logger.info(f"Ciclo de mercado detectado: {detected_cycle.value} con confianza: {confidence:.2f}")
        return detected_cycle
    
    def get_cycle_recommendations(self) -> Dict[str, Any]:
        """Genera recomendaciones estratégicas basadas en el ciclo actual.
        
        Returns:
            Dict: Recomendaciones para estrategia de portafolio y trading
        """
        if self.current_cycle == MarketCycle.UNKNOWN:
            return {
                'risk_level': 'moderate',
                'cash_allocation': 0.30,  # 30% en efectivo por defecto
                'max_position_size': 0.05,  # 5% por posición
                'strategy_focus': 'balanced',
                'rebalance_frequency': 'normal',
                'recommendation': 'Mantener estrategia balanceada hasta detectar ciclo claro'
            }
            
        # Recomendaciones específicas para cada fase del ciclo
        if self.current_cycle == MarketCycle.ACCUMULATION:
            return {
                'risk_level': 'moderate',
                'cash_allocation': 0.20,  # Reducir efectivo para acumular activos
                'max_position_size': 0.05,
                'strategy_focus': 'value',
                'rebalance_frequency': 'low',
                'recommendation': 'Fase de acumulación: Comprar gradualmente activos fundamentalmente sólidos, enfoque DCA'
            }
            
        elif self.current_cycle == MarketCycle.UPTREND:
            return {
                'risk_level': 'aggressive',
                'cash_allocation': 0.10,  # Menor efectivo para maximizar exposición
                'max_position_size': 0.10,  # Posiciones mayores
                'strategy_focus': 'growth',
                'rebalance_frequency': 'high',
                'recommendation': 'Tendencia alcista: Aumentar exposición a activos de alto crecimiento, mantener stop-loss amplios'
            }
            
        elif self.current_cycle == MarketCycle.DISTRIBUTION:
            return {
                'risk_level': 'conservative',
                'cash_allocation': 0.40,  # Aumentar efectivo
                'max_position_size': 0.03,  # Reducir tamaño de posiciones
                'strategy_focus': 'profit_taking',
                'rebalance_frequency': 'high',
                'recommendation': 'Fase de distribución: Tomar beneficios gradualmente, aumentar reservas de efectivo'
            }
            
        elif self.current_cycle == MarketCycle.DOWNTREND:
            return {
                'risk_level': 'defensive',
                'cash_allocation': 0.60,  # Máximo efectivo para preservar capital
                'max_position_size': 0.02,  # Posiciones mínimas
                'strategy_focus': 'capital_preservation',
                'rebalance_frequency': 'low',
                'recommendation': 'Tendencia bajista: Priorizar preservación de capital, mantener alta proporción de efectivo/stablecoins'
            }
            
        # Caso de respaldo
        return {
            'risk_level': 'moderate',
            'cash_allocation': 0.30,
            'max_position_size': 0.05,
            'strategy_focus': 'balanced',
            'rebalance_frequency': 'normal',
            'recommendation': 'Mantener estrategia balanceada'
        }
    
    def get_historical_cycles(self, days: int = 180) -> List[Dict[str, Any]]:
        """Obtiene el historial de ciclos detectados en el período especificado.
        
        Args:
            days: Número de días hacia atrás para obtener el historial
            
        Returns:
            List[Dict]: Historial de ciclos detectados con sus métricas
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        return [cycle for cycle in self.cycle_history 
                if cycle['timestamp'] > cutoff_date]
