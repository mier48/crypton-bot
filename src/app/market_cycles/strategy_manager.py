from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

from src.config.settings import settings
from src.app.market_cycles.detector import MarketCycle, MarketCycleDetector
from src.app.market_cycles.integrator import MarketCycleIntegrator

class AdaptiveStrategyManager:
    """
    Gestor central de estrategias adaptativas basadas en ciclos de mercado.
    
    Este componente orquesta la interacción entre los diferentes sistemas del bot,
    adaptando su comportamiento según la fase del ciclo de mercado actual:
    
    1. Coordina el detector de ciclos de mercado con el resto del sistema
    2. Ajusta dinámicamente los parámetros de riesgo y asignación
    3. Integra con el detector de burbujas para protección adicional
    4. Modifica la estrategia de inversión proporcional al riesgo
    5. Adapta los criterios de rebalanceo del portafolio
    """
    
    def __init__(self, data_manager):
        """
        Inicializa el gestor de estrategias adaptativas.
        
        Args:
            data_manager: Gestor de datos para obtener información de mercado
        """
        self.data_manager = data_manager
        self.cycle_integrator = MarketCycleIntegrator(data_manager)
        
        # Estado de adaptación
        self.last_update_time = None
        self.adaptation_active = True
        self.current_adaptations = {}
        
        # Intervalo de actualización de ciclo (cada 8 horas por defecto)
        self.update_interval_hours = 8
        
        # Configuraciones
        self.load_settings()
        
        logger.info("Sistema de adaptación a ciclos de mercado inicializado")
        
    def load_settings(self):
        """Carga configuraciones desde settings."""
        self.adaptation_active = getattr(settings, 'ENABLE_MARKET_CYCLE_ADAPTATION', True)
        self.update_interval_hours = getattr(settings, 'MARKET_CYCLE_UPDATE_INTERVAL', 8)
        
    def update_market_state(self, force: bool = False) -> Dict[str, Any]:
        """
        Actualiza el estado del mercado y aplica adaptaciones.
        
        Args:
            force: Si es True, fuerza una actualización aunque se haya actualizado recientemente
            
        Returns:
            Dict[str, Any]: Las adaptaciones aplicadas
        """
        if not self.adaptation_active:
            logger.info("Sistema de adaptación a ciclos de mercado desactivado")
            return {}
            
        # Verificar si es necesario actualizar
        current_time = datetime.now()
        if not force and self.last_update_time:
            hours_since_update = (current_time - self.last_update_time).total_seconds() / 3600
            if hours_since_update < self.update_interval_hours:
                logger.debug(f"Usando adaptaciones existentes (actualizado hace {hours_since_update:.1f} horas)")
                return self.current_adaptations
        
        # Obtener datos de mercado para analizarlos
        market_data = self._get_market_data()
        if not market_data or len(market_data.get('BTC', pd.DataFrame())) < 30:
            logger.warning("Datos insuficientes para actualizar ciclo de mercado")
            return self.current_adaptations
            
        # Actualizar ciclo de mercado
        self.cycle_integrator.update_market_cycle(market_data, force_update=force)
        
        # Obtener estado de portafolio actual para adaptaciones
        portfolio_state = self._get_portfolio_state()
        
        # Obtener adaptaciones para todo el sistema
        adaptations = self.cycle_integrator.apply_cycle_adaptations(portfolio_state)
        
        # Guardar adaptaciones actuales
        self.current_adaptations = adaptations
        self.last_update_time = current_time
        
        # Log informativo
        current_cycle = self.cycle_integrator.current_cycle.value
        confidence = self.cycle_integrator.cycle_confidence
        logger.info(f"Ciclo actual: {current_cycle} (Confianza: {confidence:.2f}) - "
                  f"Adaptaciones aplicadas: {len(adaptations)} componentes")
        
        return adaptations
    
    def _get_market_data(self) -> Dict[str, pd.DataFrame]:
        """Obtiene datos de mercado necesarios para el análisis."""
        market_data = {}
        try:
            # Calcular fechas para 90 días
            end_time = int(datetime.now().timestamp() * 1000)
            start_time = int((datetime.now() - timedelta(days=90)).timestamp() * 1000)
            
            # Obtener datos de BTC (esencial para la detección)
            btc_klines = self.data_manager.fetch_historical_data(
                symbol="BTCUSDT",
                interval="1d",
                start_time=start_time,
                end_time=end_time,
                limit=90  # 90 días
            )
            
            if btc_klines is not None and len(btc_klines) > 0:
                # Convertir a DataFrame
                btc_df = pd.DataFrame(btc_klines, columns=[
                    'open_time', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                ])
                
                # Convertir a tipos adecuados
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    btc_df[col] = btc_df[col].astype(float)
                    
                market_data['BTC'] = btc_df
            
            # Intentar obtener datos de ETH también
            try:
                eth_klines = self.data_manager.fetch_historical_data(
                    symbol="ETHUSDT",
                    interval="1d",
                    start_time=start_time,
                    end_time=end_time,
                    limit=90  # 90 días
                )
                
                if eth_klines is not None and len(eth_klines) > 0:
                    eth_df = pd.DataFrame(eth_klines, columns=[
                        'open_time', 'open', 'high', 'low', 'close', 'volume',
                        'close_time', 'quote_asset_volume', 'number_of_trades',
                        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
                    ])
                    
                    for col in ['open', 'high', 'low', 'close', 'volume']:
                        eth_df[col] = eth_df[col].astype(float)
                        
                    market_data['ETH'] = eth_df
            except Exception as e:
                logger.warning(f"No se pudieron obtener datos de ETH: {e}")
                
        except Exception as e:
            logger.error(f"Error obteniendo datos de mercado: {e}")
            
        return market_data
    
    def _get_portfolio_state(self):
        """Obtiene el estado actual del portafolio."""
        # En un entorno real, aquí obtendremos el estado del portafolio
        # para ahora simplemente devolvemos None y lo manejamos en el integrador
        return None
    
    def get_current_cycle_info(self) -> Dict[str, Any]:
        """Obtiene información detallada sobre el ciclo de mercado actual."""
        return self.cycle_integrator.get_current_cycle_info()
    
    def modify_buy_parameters(self, buy_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modifica los parámetros de compra según el ciclo de mercado actual.
        
        Args:
            buy_params: Parámetros originales de compra
            
        Returns:
            Dict[str, Any]: Parámetros modificados
        """
        if not self.adaptation_active or not self.current_adaptations:
            return buy_params
            
        buy_adaptations = self.current_adaptations.get('buy_manager', {})
        if not buy_adaptations:
            return buy_params
            
        # Copiar parámetros originales
        modified_params = buy_params.copy()
        
        # Aplicar modificaciones según el ciclo
        current_cycle = self.cycle_integrator.current_cycle
        
        # 1. Adaptar cantidad de inversión
        if 'investment_amount' in modified_params and 'investment_multiplier' in buy_adaptations:
            modified_params['investment_amount'] *= buy_adaptations['investment_multiplier']
            
        # 2. Adaptar umbral de confianza (integración con sistema de inversión proporcional al riesgo)
        if 'confidence_threshold' in buy_adaptations:
            modified_params['confidence_threshold'] = buy_adaptations['confidence_threshold']
            
        # 3. Adaptar criterios de evaluación según ciclo
        if current_cycle == MarketCycle.UPTREND:
            # En mercado alcista, enfocarse en momentum y tendencias
            modified_params['trend_weight'] = 0.6       # Dar mayor peso a tendencias
            modified_params['volume_weight'] = 0.4      # Y al volumen
        elif current_cycle == MarketCycle.DISTRIBUTION:
            # En distribución, enfocarse en señales de reversión
            modified_params['oscillator_weight'] = 0.5   # Mayor peso a osciladores (RSI, etc)
            modified_params['divergence_weight'] = 0.5   # Y a divergencias
        elif current_cycle == MarketCycle.DOWNTREND:
            # En mercado bajista, ser muy selectivo
            modified_params['risk_filter'] = 'high'      # Mayor filtrado de riesgo
            modified_params['min_confidence'] = 85       # Exigir alta confianza
            
        # 4. Integración con el detector de burbujas
        if 'bubble_threshold' in modified_params:
            if current_cycle == MarketCycle.UPTREND:
                # En ciclo alcista, ser más permisivo con posibles burbujas
                modified_params['bubble_threshold'] *= 1.2  # 20% más permisivo
            elif current_cycle in [MarketCycle.DISTRIBUTION, MarketCycle.DOWNTREND]:
                # En distribución/bajista, ser más estricto
                modified_params['bubble_threshold'] *= 0.8  # 20% más restrictivo
                
        logger.debug(f"Parámetros de compra adaptados al ciclo {current_cycle.value}")
        return modified_params
    
    def modify_sell_parameters(self, sell_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modifica los parámetros de venta según el ciclo de mercado actual.
        
        Args:
            sell_params: Parámetros originales de venta
            
        Returns:
            Dict[str, Any]: Parámetros modificados
        """
        if not self.adaptation_active or not self.current_adaptations:
            return sell_params
            
        sell_adaptations = self.current_adaptations.get('sell_manager', {})
        if not sell_adaptations:
            return sell_params
            
        # Copiar parámetros originales
        modified_params = sell_params.copy()
        
        # Aplicar modificaciones según el ciclo
        current_cycle = self.cycle_integrator.current_cycle
        
        # 1. Adaptar stop loss y take profit
        if 'stop_loss_pct' in modified_params and 'stop_loss_multiplier' in sell_adaptations:
            modified_params['stop_loss_pct'] *= sell_adaptations['stop_loss_multiplier']
            
        if 'take_profit_pct' in modified_params and 'take_profit_multiplier' in sell_adaptations:
            modified_params['take_profit_pct'] *= sell_adaptations['take_profit_multiplier']
            
        # 2. Adaptar agresividad en toma de beneficios
        if 'profit_taking_aggressiveness' in sell_adaptations:
            # Por ejemplo, en distribución ser más agresivo tomando beneficios
            if sell_adaptations['profit_taking_aggressiveness'] == 'high':
                # Vender más rápido
                if 'trailing_stop_activation' in modified_params:
                    modified_params['trailing_stop_activation'] *= 0.8  # Activar trailing stop antes
                if 'partial_take_profit' in modified_params:
                    modified_params['partial_take_profit'] = True      # Tomar beneficios parciales
            
        # 3. Integración con el detector de burbujas
        if current_cycle == MarketCycle.DISTRIBUTION and 'use_bubble_detection' in modified_params:
            # En fase de distribución, priorizar venta cuando se detecten burbujas
            modified_params['use_bubble_detection'] = True
            if 'bubble_sensitivity' in modified_params:
                modified_params['bubble_sensitivity'] *= 1.3  # 30% más sensible a burbujas
                
        logger.debug(f"Parámetros de venta adaptados al ciclo {current_cycle.value}")
        return modified_params
    
    def modify_portfolio_parameters(self, portfolio_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modifica los parámetros de gestión de portafolio según el ciclo de mercado.
        
        Args:
            portfolio_params: Parámetros originales del portafolio
            
        Returns:
            Dict[str, Any]: Parámetros modificados
        """
        if not self.adaptation_active or not self.current_adaptations:
            return portfolio_params
            
        portfolio_adaptations = self.current_adaptations.get('portfolio', {})
        if not portfolio_adaptations:
            return portfolio_params
            
        # Copiar parámetros originales
        modified_params = portfolio_params.copy()
        
        # Aplicar modificaciones según el ciclo
        
        # 1. Adaptar aversión al riesgo
        if 'risk_aversion' in portfolio_adaptations:
            modified_params['risk_aversion'] = portfolio_adaptations['risk_aversion']
            
        # 2. Adaptar asignación máxima por activo
        if 'max_allocation_per_asset' in portfolio_adaptations:
            modified_params['max_allocation_per_asset'] = portfolio_adaptations['max_allocation_per_asset']
            
        # 3. Adaptar reserva de efectivo
        if 'cash_reserve' in portfolio_adaptations:
            modified_params['cash_reserve'] = portfolio_adaptations['cash_reserve']
            
        # 4. Adaptar frecuencia de rebalanceo
        if 'rebalance_frequency' in portfolio_adaptations:
            modified_params['rebalance_frequency'] = portfolio_adaptations['rebalance_frequency']
            
            # Traducir frecuencia de rebalanceo a horas
            if portfolio_adaptations['rebalance_frequency'] == 'high':
                modified_params['rebalance_check_hours'] = 4  # Cada 4 horas
            elif portfolio_adaptations['rebalance_frequency'] == 'normal':
                modified_params['rebalance_check_hours'] = 12  # Cada 12 horas
            elif portfolio_adaptations['rebalance_frequency'] == 'low':
                modified_params['rebalance_check_hours'] = 24  # Diario
                
        logger.debug(f"Parámetros de portafolio adaptados al ciclo {self.cycle_integrator.current_cycle.value}")
        return modified_params
