from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

from src.config.settings import settings
from src.app.market_cycles.detector import MarketCycleDetector, MarketCycle
from src.app.portfolio.models.portfolio_state import PortfolioState
from src.app.notifiers.telegram_notifier import TelegramNotifier

class MarketCycleIntegrator:
    """
    Integra el detector de ciclos de mercado con el resto del sistema.
    
    Este componente permite adaptar dinámicamente las estrategias de trading
    y gestión de portafolio según la fase actual del ciclo de mercado, optimizando
    el rendimiento en diferentes condiciones de mercado.
    """
    
    def __init__(self, data_manager=None):
        """
        Inicializa el integrador de ciclos de mercado.
        
        Args:
            data_manager: Gestor de datos para obtener información de mercado
        """
        self.data_manager = data_manager
        self.cycle_detector = MarketCycleDetector(lookback_days=90)
        
        # Inicializar notificador de Telegram
        self.telegram_notifier = TelegramNotifier()
        self.enable_notifications = getattr(settings, 'NOTIFY_MARKET_CYCLE_CHANGES', True)
        
        # Configuraciones según ciclo de mercado
        self.cycle_config = {
            MarketCycle.ACCUMULATION: {
                'risk_aversion': 0.5,              # Riesgo moderado
                'max_allocation_per_asset': 0.15,  # 15% máximo por activo
                'cash_reserve': 0.20,              # 20% en stablecoins
                'trading_frequency': 'medium',     # Frecuencia media de trading
                'stop_loss_multiplier': 1.0,       # Stop loss estándar
                'take_profit_multiplier': 1.2,     # Take profit ligeramente mayor
                'dca_enabled': True                # Habilitar DCA (Dollar Cost Averaging)
            },
            MarketCycle.UPTREND: {
                'risk_aversion': 0.3,              # Menor aversión al riesgo
                'max_allocation_per_asset': 0.25,  # 25% máximo por activo
                'cash_reserve': 0.10,              # 10% en stablecoins
                'trading_frequency': 'high',       # Mayor frecuencia de trading
                'stop_loss_multiplier': 0.8,       # Stop loss más amplio
                'take_profit_multiplier': 1.5,     # Take profit más ambicioso
                'dca_enabled': False               # Desactivar DCA
            },
            MarketCycle.DISTRIBUTION: {
                'risk_aversion': 0.7,              # Mayor aversión al riesgo
                'max_allocation_per_asset': 0.10,  # 10% máximo por activo
                'cash_reserve': 0.40,              # 40% en stablecoins
                'trading_frequency': 'high',       # Mayor frecuencia para tomar beneficios
                'stop_loss_multiplier': 0.7,       # Stop loss más ajustado
                'take_profit_multiplier': 1.0,     # Take profit conservador
                'dca_enabled': False               # Desactivar DCA
            },
            MarketCycle.DOWNTREND: {
                'risk_aversion': 0.9,              # Máxima aversión al riesgo
                'max_allocation_per_asset': 0.05,  # 5% máximo por activo
                'cash_reserve': 0.60,              # 60% en stablecoins
                'trading_frequency': 'low',        # Baja frecuencia de trading
                'stop_loss_multiplier': 0.5,       # Stop loss muy ajustado
                'take_profit_multiplier': 0.8,     # Take profit conservador
                'dca_enabled': True                # Habilitar DCA para promediar a la baja
            },
            MarketCycle.UNKNOWN: {
                'risk_aversion': 0.6,              # Riesgo moderado
                'max_allocation_per_asset': 0.15,  # 15% máximo por activo
                'cash_reserve': 0.30,              # 30% en stablecoins
                'trading_frequency': 'medium',     # Frecuencia media
                'stop_loss_multiplier': 0.9,       # Stop loss estándar
                'take_profit_multiplier': 1.1,     # Take profit estándar
                'dca_enabled': False               # Sin DCA
            }
        }
        
        # Ciclo actual y recomendaciones
        self.current_cycle = MarketCycle.UNKNOWN
        self.cycle_confidence = 0.0
        self.last_detection_time = None
        self.active_config = self.cycle_config[MarketCycle.UNKNOWN].copy()
        
    def update_market_cycle(self, market_data: Dict[str, pd.DataFrame], force_update: bool = False) -> MarketCycle:
        """
        Actualiza la detección del ciclo de mercado actual.
        
        Args:
            market_data: Diccionario con datos de mercado para diferentes activos
            force_update: Si es True, fuerza una actualización aunque se haya detectado recientemente
            
        Returns:
            MarketCycle: El ciclo de mercado detectado
        """
        # Verificar si es necesario actualizar
        current_time = datetime.now()
        if not force_update and self.last_detection_time:
            hours_since_update = (current_time - self.last_detection_time).total_seconds() / 3600
            if hours_since_update < 6:  # Actualizar máximo cada 6 horas
                logger.debug(f"Usando detección de ciclo existente: {self.current_cycle.value} (actualizado hace {hours_since_update:.1f} horas)")
                return self.current_cycle
        
        # Extraer datos relevantes para la detección
        btc_data = market_data.get('BTC', None)
        eth_data = market_data.get('ETH', None)
        
        if btc_data is None or len(btc_data) < 30:
            logger.warning("Datos insuficientes para detectar ciclo de mercado")
            return MarketCycle.UNKNOWN
        
        # Obtener datos de sentimiento si están disponibles
        sentiment_data = None
        if hasattr(self.data_manager, 'get_market_sentiment'):
            try:
                sentiment_data = self.data_manager.get_market_sentiment()
            except Exception as e:
                logger.warning(f"No se pudieron obtener datos de sentimiento: {e}")
        
        # Detectar ciclo actual
        self.current_cycle = self.cycle_detector.detect_market_cycle(
            btc_data=btc_data,
            eth_data=eth_data,
            market_data=market_data,
            sentiment_data=sentiment_data
        )
        
        self.cycle_confidence = self.cycle_detector.confidence_score
        self.last_detection_time = current_time
        
        # Detectar si hubo un cambio de ciclo
        previous_cycle = self.current_cycle
        
        # Actualizar la configuración activa según el ciclo detectado
        self.active_config = self.cycle_config[self.current_cycle].copy()
        
        logger.info(f"Ciclo de mercado actualizado: {self.current_cycle.value} "
                   f"(Confianza: {self.cycle_confidence:.2f})")
                   
        # Enviar notificación si el ciclo cambió
        if previous_cycle != self.current_cycle and self.enable_notifications:
            self.send_cycle_change_notification(previous_cycle, self.current_cycle)
            
        return self.current_cycle
    
    def apply_cycle_adaptations(self, portfolio_state: PortfolioState) -> Dict[str, Any]:
        """
        Aplica adaptaciones a la estrategia según el ciclo de mercado actual.
        
        Args:
            portfolio_state: Estado actual del portafolio
            
        Returns:
            Dict[str, Any]: Configuraciones adaptadas para el sistema
        """
        # Verificar si tenemos un ciclo detectado
        if self.current_cycle == MarketCycle.UNKNOWN:
            logger.info("Usando configuración estándar (ciclo desconocido)")
            return {}
        
        # Obtener recomendaciones del detector de ciclos
        recommendations = self.cycle_detector.get_cycle_recommendations()
        
        # Adaptaciones para el sistema de portafolio
        portfolio_adaptations = {
            # Parámetros para AllocationCalculator
            'risk_aversion': self.active_config['risk_aversion'],
            'max_allocation_per_asset': self.active_config['max_allocation_per_asset'],
            'cash_reserve': self.active_config['cash_reserve'],
            
            # Frecuencia de rebalanceo basada en el ciclo
            'rebalance_frequency': 'high' if self.current_cycle in [MarketCycle.UPTREND, MarketCycle.DISTRIBUTION] else 'normal',
            
            # Comunicar el ciclo actual para decisiones de trading
            'market_cycle': self.current_cycle.value,
            'cycle_confidence': self.cycle_confidence,
            
            # Transmitir recomendaciones
            'recommendations': recommendations
        }
        
        # Adaptaciones para el gestor de compras
        buy_adaptations = {
            # Ajustar importes de compra según el ciclo
            'investment_multiplier': 1.5 if self.current_cycle == MarketCycle.ACCUMULATION else 
                                    1.3 if self.current_cycle == MarketCycle.UPTREND else 
                                    0.8 if self.current_cycle == MarketCycle.DISTRIBUTION else 
                                    0.5,  # DOWNTREND
                                    
            # Umbral de confianza requerido para compras
            'confidence_threshold': 60 if self.current_cycle == MarketCycle.ACCUMULATION else 
                                  70 if self.current_cycle == MarketCycle.UPTREND else 
                                  80 if self.current_cycle == MarketCycle.DISTRIBUTION else 
                                  90,  # DOWNTREND - Máxima exigencia
                                  
            # Activar/desactivar DCA
            'dca_enabled': self.active_config['dca_enabled']
        }
        
        # Adaptaciones para el gestor de ventas
        sell_adaptations = {
            # Multiplicadores para stop loss y take profit
            'stop_loss_multiplier': self.active_config['stop_loss_multiplier'],
            'take_profit_multiplier': self.active_config['take_profit_multiplier'],
            
            # Agresividad en toma de beneficios
            'profit_taking_aggressiveness': 'high' if self.current_cycle == MarketCycle.DISTRIBUTION else 
                                          'medium' if self.current_cycle == MarketCycle.UPTREND else 
                                          'low'
        }
        
        # Combinar todas las adaptaciones
        adaptations = {
            'portfolio': portfolio_adaptations,
            'buy_manager': buy_adaptations,
            'sell_manager': sell_adaptations,
            'market_cycle': {
                'current': self.current_cycle.value,
                'confidence': self.cycle_confidence,
                'last_updated': self.last_detection_time.isoformat() if self.last_detection_time else None
            }
        }
        
        logger.info(f"Aplicando adaptaciones para ciclo {self.current_cycle.value}")
        
        # Enviar notificación detallada de adaptaciones si está habilitado
        if self.enable_notifications and hasattr(settings, 'NOTIFY_ADAPTATION_DETAILS') and settings.NOTIFY_ADAPTATION_DETAILS:
            self.send_adaptation_notification(adaptations)
            
        return adaptations
    
    def get_current_cycle_info(self) -> Dict[str, Any]:
        """
        Obtiene información detallada sobre el ciclo de mercado actual.
        
        Returns:
            Dict[str, Any]: Información del ciclo actual y recomendaciones
        """
        if self.current_cycle == MarketCycle.UNKNOWN:
            return {
                'cycle': 'unknown',
                'confidence': 0.0,
                'description': 'No se ha detectado un ciclo claro',
                'recommendations': 'Mantener estrategia balanceada',
                'last_updated': None
            }
        
        # Descripción detallada según el ciclo
        cycle_descriptions = {
            MarketCycle.ACCUMULATION: (
                "Fase de acumulación: El mercado se encuentra cerca de mínimos y en "
                "consolidación lateral después de una fase bajista. Los inversores "
                "institucionales comienzan a acumular mientras el sentimiento general "
                "sigue siendo negativo."
            ),
            MarketCycle.UPTREND: (
                "Fase alcista: El mercado ha confirmado una tendencia alcista con "
                "aumento de volumen y ruptura de resistencias clave. Los activos muestran "
                "momentum positivo y el sentimiento mejora progresivamente."
            ),
            MarketCycle.DISTRIBUTION: (
                "Fase de distribución: El mercado se encuentra cerca de máximos y muestra "
                "signos de agotamiento alcista. Hay divergencias en indicadores clave y "
                "el sentimiento es extremadamente optimista, característico de la fase "
                "final de un ciclo alcista."
            ),
            MarketCycle.DOWNTREND: (
                "Fase bajista: El mercado ha confirmado una tendencia bajista con "
                "rupturas de soportes clave y aumento de volatilidad. Predomina el "
                "sentimiento negativo y los activos muestran debilidad generalizada."
            )
        }
        
        recommendations = self.cycle_detector.get_cycle_recommendations()
        
        return {
            'cycle': self.current_cycle.value,
            'confidence': self.cycle_confidence,
            'description': cycle_descriptions.get(self.current_cycle, ""),
            'recommendations': recommendations.get('recommendation', ""),
            'risk_level': recommendations.get('risk_level', 'moderate'),
            'suggested_cash': recommendations.get('cash_allocation', 0.3),
            'metrics': self.cycle_detector.cycle_metrics,
            'last_updated': self.last_detection_time.isoformat() if self.last_detection_time else None,
            'history': self.cycle_detector.get_historical_cycles(days=90)
        }
        
    def send_cycle_change_notification(self, previous_cycle: MarketCycle, new_cycle: MarketCycle) -> None:
        """
        Envía una notificación a Telegram cuando cambia el ciclo de mercado.
        
        Args:
            previous_cycle: Ciclo anterior
            new_cycle: Nuevo ciclo detectado
        """
        if not self.enable_notifications:
            return
            
        # Emojis para cada ciclo
        cycle_emojis = {
            MarketCycle.ACCUMULATION: "🔄",   # Ciclo de acumulación
            MarketCycle.UPTREND: "📈",       # Tendencia alcista
            MarketCycle.DISTRIBUTION: "🔝",   # Distribución
            MarketCycle.DOWNTREND: "📉",     # Tendencia bajista
            MarketCycle.UNKNOWN: "❓"        # Desconocido
        }
        
        # Descripciones cortas de cada ciclo
        cycle_descriptions = {
            MarketCycle.ACCUMULATION: "fase de acumulación (consolidación lateral)",
            MarketCycle.UPTREND: "tendencia alcista (ruptura alcista)",
            MarketCycle.DISTRIBUTION: "fase de distribución (cerca de máximos)",
            MarketCycle.DOWNTREND: "tendencia bajista (mercado en caída)",
            MarketCycle.UNKNOWN: "ciclo desconocido (datos insuficientes)"
        }
        
        # Adaptaciones principales
        adaptations = {
            MarketCycle.ACCUMULATION: "Riesgo moderado, DCA activado",
            MarketCycle.UPTREND: "Menor aversión al riesgo, take profits mayores",
            MarketCycle.DISTRIBUTION: "Mayor aversión al riesgo, preparado para tomar beneficios",
            MarketCycle.DOWNTREND: "Máxima aversión al riesgo, alta reserva de efectivo",
            MarketCycle.UNKNOWN: "Configuración estándar, riesgo equilibrado"
        }
        
        # Confianza
        confidence_str = f"{self.cycle_confidence * 100:.1f}%"
        
        # Construir mensaje
        emoji = cycle_emojis.get(new_cycle, "⚠️")
        title = f"{emoji} *CAMBIO EN EL CICLO DE MERCADO* {emoji}"
        
        message = (
            f"{title}\n\n"
            f"🔄 *Ciclo anterior:* {previous_cycle.value}\n"
            f"🆕 *Nuevo ciclo:* {new_cycle.value}\n"
            f"🎯 *Confianza:* {confidence_str}\n"
            f"📝 *Descripción:* {cycle_descriptions.get(new_cycle, 'Desconocido')}\n\n"
            f"⚙️ *Adaptaciones:*\n{adaptations.get(new_cycle, 'Sin adaptaciones')}\n\n"
            f"📊 *Recomendaciones:*\n"
        )
        
        # Añadir recomendaciones específicas
        if new_cycle == MarketCycle.ACCUMULATION:
            message += "• Acumular activos de calidad a precios favorables\n"
            message += "• Mantener una posición de efectivo moderada"
        elif new_cycle == MarketCycle.UPTREND:
            message += "• Aumentar exposición a activos con momentum positivo\n"
            message += "• Elevar take profits y usar trailing stops"
        elif new_cycle == MarketCycle.DISTRIBUTION:
            message += "• Tomar beneficios gradualmente\n"
            message += "• Aumentar reserva de efectivo para próximas oportunidades"
        elif new_cycle == MarketCycle.DOWNTREND:
            message += "• Reducir significativamente la exposición al riesgo\n"
            message += "• Mantener alta reserva de efectivo y esperar mejores entradas"
        else:
            message += "• Mantener estrategia equilibrada hasta tener más datos"
            
        # Enviar la notificación
        try:
            self.telegram_notifier.send_message(message)
            logger.info(f"Notificación de cambio de ciclo enviada a Telegram")
        except Exception as e:
            logger.error(f"Error al enviar notificación de cambio de ciclo: {e}")
            
    def send_adaptation_notification(self, adaptations: Dict[str, Any]) -> None:
        """
        Envía una notificación detallada de las adaptaciones realizadas.
        
        Args:
            adaptations: Diccionario con las adaptaciones aplicadas
        """
        if not self.enable_notifications:
            return
            
        # Emoji para el ciclo actual
        cycle_emojis = {
            'accumulation': "🔄",  # Acumulación
            'uptrend': "📈",      # Alcista
            'distribution': "🔝",  # Distribución
            'downtrend': "📉",    # Bajista
            'unknown': "❓"       # Desconocido
        }
        
        # Obtener información del ciclo
        market_cycle = adaptations.get('market_cycle', {})
        current_cycle = market_cycle.get('current', 'unknown')
        confidence = market_cycle.get('confidence', 0.0)
        last_updated = market_cycle.get('last_updated', 'N/A')
        
        # Obtener las adaptaciones específicas
        portfolio_adaptations = adaptations.get('portfolio', {})
        buy_adaptations = adaptations.get('buy_manager', {})
        sell_adaptations = adaptations.get('sell_manager', {})
        
        # Construir mensaje
        emoji = cycle_emojis.get(current_cycle, "⚠️")
        title = f"{emoji} *ADAPTACIONES AL CICLO DE MERCADO* {emoji}"
        
        message = (
            f"{title}\n\n"
            f"🔍 *Ciclo actual:* {current_cycle}\n"
            f"🎯 *Confianza:* {confidence * 100:.1f}%\n"
            f"🕒 *Última actualización:* {last_updated}\n\n"
        )
        
        # Adaptaciones del portafolio
        if portfolio_adaptations:
            message += "📊 *Adaptaciones del portafolio:*\n"
            if 'risk_aversion' in portfolio_adaptations:
                message += f"• Aversión al riesgo: {portfolio_adaptations['risk_aversion']:.2f}\n"
            if 'max_allocation_per_asset' in portfolio_adaptations:
                message += f"• Asignación máxima por activo: {portfolio_adaptations['max_allocation_per_asset']*100:.1f}%\n"
            if 'cash_reserve' in portfolio_adaptations:
                message += f"• Reserva de efectivo: {portfolio_adaptations['cash_reserve']*100:.1f}%\n"
            if 'rebalance_frequency' in portfolio_adaptations:
                message += f"• Frecuencia de rebalanceo: {portfolio_adaptations['rebalance_frequency']}\n"
            message += "\n"
            
        # Adaptaciones de compra
        if buy_adaptations:
            message += "🟢 *Adaptaciones de compra:*\n"
            if 'investment_multiplier' in buy_adaptations:
                message += f"• Multiplicador de inversión: {buy_adaptations['investment_multiplier']:.2f}\n"
            if 'confidence_threshold' in buy_adaptations:
                message += f"• Umbral de confianza: {buy_adaptations['confidence_threshold']}\n"
            if 'dca_enabled' in buy_adaptations:
                message += f"• DCA activado: {'Sí' if buy_adaptations['dca_enabled'] else 'No'}\n"
            message += "\n"
            
        # Adaptaciones de venta
        if sell_adaptations:
            message += "🔴 *Adaptaciones de venta:*\n"
            if 'stop_loss_multiplier' in sell_adaptations:
                message += f"• Multiplicador de stop loss: {sell_adaptations['stop_loss_multiplier']:.2f}\n"
            if 'take_profit_multiplier' in sell_adaptations:
                message += f"• Multiplicador de take profit: {sell_adaptations['take_profit_multiplier']:.2f}\n"
            if 'profit_taking_aggressiveness' in sell_adaptations:
                message += f"• Agresividad toma de beneficios: {sell_adaptations['profit_taking_aggressiveness']}\n"
                
        # Enviar la notificación
        try:
            self.telegram_notifier.send_message(message)
            logger.info(f"Notificación de adaptaciones enviada a Telegram")
        except Exception as e:
            logger.error(f"Error al enviar notificación de adaptaciones: {e}")
