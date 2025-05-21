"""
RiskManager: módulo para gestión de riesgos,
- límites de exposición
- cálculo de VaR
- stop-loss / take-profit automáticos
- tamaño de posición dinámico según % de capital
- adaptación a ciclos de mercado"""
from typing import List, Dict, Any, Optional
import numpy as np
from datetime import datetime
from loguru import logger

from config.settings import settings
from src.app.market_cycles.strategy_manager import AdaptiveStrategyManager


class RiskManager:
    def __init__(self, data_provider, executor):
        self.data_provider = data_provider
        self.executor = executor
        # Límites de capital (porcentaje) y riesgo
        self.max_exposure_pct = settings.MAX_EXPOSURE_PERCENT / 100
        self.risk_per_trade_pct = settings.RISK_PER_TRADE_PERCENT / 100
        
        # Sistema de adaptación a ciclos de mercado
        self.enable_market_cycle_adaptation = settings.ENABLE_MARKET_CYCLE_ADAPTATION
        self.strategy_manager = None
        if self.enable_market_cycle_adaptation:
            try:
                self.strategy_manager = AdaptiveStrategyManager(data_provider)
                logger.info("Sistema de adaptación a ciclos de mercado inicializado correctamente")
            except Exception as e:
                logger.error(f"Error al inicializar el sistema de adaptación a ciclos de mercado: {e}")
                self.enable_market_cycle_adaptation = False

    def calculate_var(self, returns: List[float], confidence: float = 0.95) -> float:
        """
        Calcula el Value at Risk (VaR) a un nivel de confianza.
        """
        sorted_r = sorted(returns)
        index = int((1 - confidence) * len(sorted_r))
        return abs(sorted_r[index]) if sorted_r else 0.0

    def position_size(self, capital: float, stop_loss_pct: float) -> float:
        """
        Determina tamaño de la posición basado en % de riesgo y stop-loss.
        Adaptado al ciclo de mercado actual.
        """
        # Aplicar adaptación según ciclo de mercado si está habilitado
        risk_multiplier = 1.0
        if self.enable_market_cycle_adaptation and self.strategy_manager:
            try:
                # Actualizar ciclo de mercado si es necesario
                self.strategy_manager.update_market_state()
                current_cycle = self.strategy_manager.cycle_integrator.current_cycle.value
                cycle_confidence = self.strategy_manager.cycle_integrator.cycle_confidence
                
                # Ajustar multiplicador de riesgo según ciclo
                if current_cycle == 'uptrend' and cycle_confidence > 0.6:
                    risk_multiplier = 1.2  # Aumentar tamaño en mercado alcista
                elif current_cycle == 'distribution' and cycle_confidence > 0.6:
                    risk_multiplier = 0.8  # Reducir tamaño en distribución
                elif current_cycle == 'downtrend' and cycle_confidence > 0.6:
                    risk_multiplier = 0.5  # Reducir significativamente en mercado bajista
                
                logger.debug(f"Tamaño de posición adaptado al ciclo {current_cycle} (x{risk_multiplier})")
            except Exception as e:
                logger.warning(f"Error al adaptar tamaño de posición al ciclo de mercado: {e}")
        
        risk_amount = capital * self.risk_per_trade_pct * risk_multiplier
        # Pérdida máxima por posición
        loss_per_unit = stop_loss_pct
        # unidades a comprar
        return risk_amount / (loss_per_unit * capital) if loss_per_unit > 0 else 0

    def current_exposure(self) -> float:
        """
        Suma el valor en USD de todas las posiciones abiertas.
        """
        balances = self.data_provider.get_balance_summary()
        total = 0.0
        for b in balances:
            asset = b['asset']
            if asset == 'USDC':
                continue
            free = float(b['free'])
            price = float(self.data_provider.get_price(asset + 'USDC'))
            total += free * price
        return total
        
    def get_market_cycle_info(self) -> Dict[str, Any]:
        """
        Obtiene información sobre el ciclo de mercado actual y las adaptaciones aplicadas.
        
        Returns:
            Dict[str, Any]: Información del ciclo actual y adaptaciones
        """
        if not self.enable_market_cycle_adaptation or not self.strategy_manager:
            return {
                'enabled': False,
                'message': "Sistema de adaptación a ciclos de mercado desactivado"
            }
            
        try:
            # Actualizar ciclo de mercado si es necesario
            self.strategy_manager.update_market_state()
            
            # Obtener información detallada
            cycle_info = self.strategy_manager.get_current_cycle_info()
            adaptations = self.strategy_manager.current_adaptations
            
            return {
                'enabled': True,
                'cycle': cycle_info,
                'adaptations': adaptations,
                'last_updated': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error al obtener información del ciclo de mercado: {e}")
            return {
                'enabled': True,
                'error': str(e)
            }
            
    def modify_buy_parameters(self, buy_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modifica los parámetros de compra según el ciclo de mercado actual.
        
        Args:
            buy_params: Parámetros originales del gestor de compras
            
        Returns:
            Dict[str, Any]: Parámetros modificados
        """
        if not self.enable_market_cycle_adaptation or not self.strategy_manager:
            return buy_params
            
        return self.strategy_manager.modify_buy_parameters(buy_params)
        
    def modify_sell_parameters(self, sell_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modifica los parámetros de venta según el ciclo de mercado actual.
        
        Args:
            sell_params: Parámetros originales del gestor de ventas
            
        Returns:
            Dict[str, Any]: Parámetros modificados
        """
        if not self.enable_market_cycle_adaptation or not self.strategy_manager:
            return sell_params
            
        return self.strategy_manager.modify_sell_parameters(sell_params)
        
    def modify_portfolio_parameters(self, portfolio_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modifica los parámetros de gestión de portafolio según el ciclo de mercado.
        
        Args:
            portfolio_params: Parámetros originales del gestor de portafolio
            
        Returns:
            Dict[str, Any]: Parámetros modificados
        """
        if not self.enable_market_cycle_adaptation or not self.strategy_manager:
            return portfolio_params
            
        return self.strategy_manager.modify_portfolio_parameters(portfolio_params)

    def can_open_position(self, price: float, size: float) -> bool:
        """
        Verifica si abrir una posición mantiene el capital dentro del límite de exposición.
        Adaptado al ciclo de mercado actual.
        """
        # Obtener saldo USDC desde balance_summary
        balances = self.data_provider.get_balance_summary()
        capital = float(next((b['free'] for b in balances if b['asset'] == 'USDC'), 0.0))
        notional = price * size
        
        # Validar que exista saldo USDC suficiente
        if capital < notional:
            return False
            
        # Aplicar límites de exposición adaptados al ciclo de mercado
        if self.enable_market_cycle_adaptation and self.strategy_manager:
            try:
                # Obtenemos la reserva de efectivo recomendada para el ciclo actual
                portfolio_adaptations = self.strategy_manager.current_adaptations.get('portfolio', {})
                if 'cash_reserve' in portfolio_adaptations:
                    cash_reserve_pct = portfolio_adaptations['cash_reserve']
                    
                    # Calcular capital disponible considerando la reserva
                    available_capital = capital * (1 - cash_reserve_pct)
                    
                    # Si la operación excede el capital disponible, rechazarla
                    if notional > available_capital:
                        current_cycle = self.strategy_manager.cycle_integrator.current_cycle.value
                        logger.info(f"Operación rechazada: excede límite de exposición adaptado al ciclo {current_cycle} "
                                  f"(reserva de efectivo: {cash_reserve_pct*100:.1f}%)")
                        return False
            except Exception as e:
                logger.warning(f"Error al aplicar límites de exposición adaptados al ciclo: {e}")
                
        return True

    def apply_stop_take(self, symbol: str, entry_price: float, stop_loss_pct: float, take_profit_pct: float):
        """
        Programa órdenes OCO: stop-loss y take-profit.
        Adaptado al ciclo de mercado actual.
        """
        # Aplicar adaptación según ciclo de mercado si está habilitado
        sl_multiplier = 1.0
        tp_multiplier = 1.0
        
        if self.enable_market_cycle_adaptation and self.strategy_manager:
            try:
                # Obtener adaptaciones para el sistema de ventas
                sell_adaptations = self.strategy_manager.current_adaptations.get('sell_manager', {})
                if sell_adaptations:
                    sl_multiplier = sell_adaptations.get('stop_loss_multiplier', 1.0)
                    tp_multiplier = sell_adaptations.get('take_profit_multiplier', 1.0)
                    
                    current_cycle = self.strategy_manager.cycle_integrator.current_cycle.value
                    logger.debug(f"Parámetros de stop-loss/take-profit adaptados al ciclo {current_cycle} "
                              f"(SL x{sl_multiplier}, TP x{tp_multiplier})")
            except Exception as e:
                logger.warning(f"Error al adaptar stop-loss/take-profit al ciclo de mercado: {e}")
        
        # Aplicar multiplicadores a los porcentajes
        adjusted_stop_loss_pct = stop_loss_pct * sl_multiplier
        adjusted_take_profit_pct = take_profit_pct * tp_multiplier
        
        # Calcular precios finales
        limit_price = entry_price * (1 + adjusted_take_profit_pct)
        stop_price = entry_price * (1 - adjusted_stop_loss_pct)
        
        self.executor.submit_oco_order(symbol, size=None, stop_price=stop_price, limit_price=limit_price)
