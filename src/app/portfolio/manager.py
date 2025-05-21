from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import time
import pandas as pd
import numpy as np
from src.config.settings import settings
from src.api.binance.data_manager import BinanceDataManager
from src.app.portfolio.models.portfolio_state import PortfolioState
from src.app.portfolio.components.data_collector import DataCollector
from src.app.portfolio.components.market_analyzer import MarketAnalyzer
from src.app.portfolio.components.allocation_calculator import AllocationCalculator
from src.app.portfolio.components.rebalancer import Rebalancer
from src.app.portfolio.components.notifier import PortfolioNotifier
from loguru import logger

class PortfolioManager:
    """
    Gestor principal de portafolio que coordina los diferentes componentes
    para optimizar la asignaciu00f3n de activos y realizar rebalanceos.
    
    Esta versiu00f3n es mu00e1s modular, delegando las diferentes responsabilidades
    a componentes especializados.
    """
    
    def __init__(self, data_manager: Optional[BinanceDataManager] = None):
        """
        Inicializa el gestor de portafolio.
        
        Args:
            data_manager: Gestor de datos de Binance (opcional)
        """
        # Inicializar el data manager si no se proporciona
        self.data_manager = data_manager or BinanceDataManager()
        
        # Parámetros de configuración
        self.risk_aversion = settings.RISK_AVERSION
        self.max_allocation = settings.MAX_ALLOCATION_PER_ASSET
        self.rebalance_threshold = settings.REBALANCE_THRESHOLD
        self.market_data_days = 30  # Días de datos históricos a analizar
        
        # Horas programadas para rebalanceo
        # Asegurar que rebalance_hours sea una lista o conjunto, no un entero
        if isinstance(settings.SCHEDULED_REBALANCE_HOURS, int):
            self.rebalance_hours = [settings.SCHEDULED_REBALANCE_HOURS]
        else:
            self.rebalance_hours = settings.SCHEDULED_REBALANCE_HOURS
        self.check_interval = settings.PORTFOLIO_CHECK_INTERVAL
        
        # Estado del portafolio
        self.state = PortfolioState()
        
        # Componentes del sistema
        self.data_collector = DataCollector(self.data_manager, self.market_data_days)
        self.market_analyzer = MarketAnalyzer()
        self.allocation_calculator = AllocationCalculator(
            risk_aversion=self.risk_aversion,
            min_allocation=0.01,
            max_allocation=self.max_allocation,
            rebalance_threshold=self.rebalance_threshold
        )
        self.rebalancer = Rebalancer(self.data_manager)
        self.notifier = PortfolioNotifier()
        
        # Indicadores de estado
        self.is_running = False
        self.last_check_time = None
    
    def start(self):
        """
        Inicia el gestor de portafolio en modo continuo.
        """
        if self.is_running:
            logger.warning("El gestor de portafolio ya estu00e1 en ejecuciu00f3n")
            return
            
        self.is_running = True
        logger.info("Iniciando gestor de portafolio en modo continuo")
        
        try:
            while self.is_running:
                # Ejecutar ciclo de verificaciu00f3n
                self.check_and_rebalance_if_needed()
                
                # Esperar para el pru00f3ximo ciclo
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("Deteniendo gestor de portafolio por solicitud del usuario")
            self.is_running = False
        except Exception as e:
            logger.error(f"Error en el ciclo principal del gestor de portafolio: {e}")
            self.is_running = False
            raise
    
    def stop(self):
        """
        Detiene el gestor de portafolio.
        """
        self.is_running = False
        logger.info("Gestor de portafolio detenido")
    
    def check_and_rebalance_if_needed(self) -> bool:
        """
        Verifica si el portafolio necesita ser rebalanceado y lo ejecuta si es necesario.
        
        Returns:
            bool: True si se realizu00f3 un rebalanceo, False en caso contrario
        """
        try:
            # Actualizar estado del portafolio
            if not self.data_collector.update_portfolio_state(self.state):
                logger.error("Error actualizando estado del portafolio")
                return False
            
            # Actualizar la hora de u00faltima verificaciu00f3n
            self.last_check_time = datetime.now()
            
            # Analizar condiciu00f3n del mercado
            market_condition, market_volatility = self.market_analyzer.analyze_market_condition(self.state)
            self.state.market_condition = market_condition
            self.state.market_volatility = market_volatility
            
            # Calcular asignaciu00f3n u00f3ptima y actualizar estado
            if not self.state.target_allocation:
                self.state.target_allocation = self.allocation_calculator.calculate_optimal_allocation(self.state)
            
            # Verificar si necesitamos rebalancear
            need_rebalance = False
            
            # 1. Verificar desviaciu00f3n significativa
            significant_deviation = self.allocation_calculator.check_significant_deviation(self.state)
            if significant_deviation:
                logger.info("Desviaciu00f3n significativa detectada, se requiere rebalanceo")
                need_rebalance = True
            
            # 2. Verificar si es hora programada para rebalanceo
            current_hour = datetime.now().hour
            if current_hour in self.rebalance_hours:
                # Evitar rebalanceos mu00faltiples en la misma hora
                if not self.state.last_rebalance_time or \
                   datetime.now() - datetime.fromtimestamp(self.state.last_rebalance_time) > timedelta(hours=1):
                    logger.info(f"Hora programada para rebalanceo: {current_hour}:00")
                    need_rebalance = True
            
            # Si se necesita rebalancear, ejecutarlo
            if need_rebalance:
                return self.execute_rebalance()
            else:
                logger.info("No se requiere rebalanceo en este momento")
                return False
                
        except Exception as e:
            logger.error(f"Error verificando estado del portafolio: {e}")
            return False
    
    def execute_rebalance(self) -> bool:
        """
        Ejecuta un rebalanceo completo del portafolio.
        
        Returns:
            bool: True si el rebalanceo fue exitoso, False en caso contrario
        """
        try:
            # Notificar inicio de rebalanceo
            self.notifier.send_rebalance_start(
                market_condition=self.state.market_condition,
                market_volatility=self.state.market_volatility
            )
            
            # Calcular asignaciu00f3n u00f3ptima (forzar recu00e1lculo)
            self.state.target_allocation = self.allocation_calculator.calculate_optimal_allocation(self.state)
            
            # Calcular operaciones de rebalanceo
            trades = self.rebalancer.calculate_rebalance_trades(self.state)
            
            if not trades:
                logger.info("No se generaron operaciones para el rebalanceo")
                return False
            
            # Ejecutar operaciones
            executed_trades = self.rebalancer.execute_rebalance(trades)
            
            # Actualizar mu00e9tricas de riesgo
            risk_metrics = self.market_analyzer.calculate_risk_metrics(self.state)
            self.state.risk_metrics = risk_metrics
            
            # Actualizar hora del u00faltimo rebalanceo
            self.state.last_rebalance_time = int(datetime.now().timestamp())
            
            # Enviar resumen del rebalanceo
            self.notifier.send_rebalance_summary(
                executed_trades=executed_trades,
                new_allocation=self.state.target_allocation,
                risk_metrics=self.state.risk_metrics
            )
            
            # Actualizar estado del portafolio despuu00e9s del rebalanceo
            self.data_collector.update_portfolio_state(self.state)
            
            # Registrar histu00f3rico de rebalanceo
            self.state.rebalance_history.append({
                'timestamp': self.state.last_rebalance_time,
                'market_condition': self.state.market_condition,
                'trades': executed_trades,
                'risk_metrics': self.state.risk_metrics
            })
            
            logger.info("Rebalanceo completado exitosamente")
            return True
            
        except Exception as e:
            logger.error(f"Error ejecutando rebalanceo: {e}")
            self.notifier.send_error(f"Error durante el rebalanceo: {e}")
            return False
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen del estado actual del portafolio.
        
        Returns:
            Dict[str, Any]: Resumen del portafolio
        """
        try:
            # Asegurar que tenemos datos actualizados
            if not self.state.current_assets:
                self.data_collector.update_portfolio_state(self.state)
                
            # Crear resumen
            summary = {
                'total_value': self.state.total_value,
                'usdc_balance': self.state.usdc_balance,
                'assets_count': len(self.state.current_assets),
                'current_allocation': self.state.current_allocation,
                'target_allocation': self.state.target_allocation,
                'market_condition': self.state.market_condition,
                'market_volatility': self.state.market_volatility,
                'risk_metrics': self.state.risk_metrics,
                'last_rebalance': self.state.last_rebalance_time,
                'rebalance_count': len(self.state.rebalance_history)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error obteniendo resumen del portafolio: {e}")
            return {
                'error': str(e),
                'total_value': 0.0,
                'assets_count': 0
            }
    
    def force_rebalance(self) -> bool:
        """
        Fuerza un rebalanceo del portafolio independientemente de las condiciones.
        
        Returns:
            bool: True si el rebalanceo fue exitoso, False en caso contrario
        """
        try:
            # Actualizar estado del portafolio
            if not self.data_collector.update_portfolio_state(self.state):
                logger.error("Error actualizando estado del portafolio para rebalanceo forzado")
                return False
            
            # Ejecutar rebalanceo
            logger.info("Iniciando rebalanceo forzado")
            return self.execute_rebalance()
            
        except Exception as e:
            logger.error(f"Error en rebalanceo forzado: {e}")
            return False
