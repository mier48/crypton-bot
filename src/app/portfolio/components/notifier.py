from typing import Dict, List, Optional, Any
from src.app.notifiers.telegram_notifier import TelegramNotifier
from loguru import logger

class PortfolioNotifier:
    """
    Componente responsable de generar y enviar notificaciones sobre el estado
    y actualizaciones del portafolio.
    """
    
    def __init__(self, telegram_notifier: Optional[TelegramNotifier] = None):
        """
        Inicializa el notificador.
        
        Args:
            telegram_notifier: Instancia del notificador de Telegram (opcional)
        """
        self.telegram_notifier = telegram_notifier or TelegramNotifier()
    
    def send_rebalance_start(self, market_condition: str, market_volatility: float) -> bool:
        """
        Envía una notificación de inicio de rebalanceo.
        
        Args:
            market_condition: Condición actual del mercado
            market_volatility: Nivel de volatilidad del mercado (0-1)
            
        Returns:
            bool: True si la notificación se envía correctamente
        """
        try:
            # Emoji según condición de mercado
            market_emoji = {
                "bullish": "\ud83d\udcc8",  # Gráfico ascendente
                "bearish": "\ud83d\udcc9",  # Gráfico descendente
                "neutral": "\u2194\ufe0f"    # Flecha horizontal
            }.get(market_condition, "\ud83d\udcc8")
            
            # Volatilidad como estrellas
            volatility_level = int(market_volatility * 5)  # 0-5 estrellas
            volatility_stars = "\u2b50" * volatility_level + "\u2606" * (5 - volatility_level)
            
            message = f"\u26a1 Iniciando rebalanceo de portafolio.\n\n"
            message += f"Condición de mercado: {market_condition.capitalize()} {market_emoji}\n"
            message += f"Volatilidad: {volatility_stars} ({market_volatility:.2f})\n"
            
            # Enviar notificación
            return self.telegram_notifier.send_message(message)
            
        except Exception as e:
            logger.error(f"Error enviando notificación de inicio de rebalanceo: {e}")
            return False
    
    def create_rebalance_summary(self, 
                             executed_trades: List[Dict], 
                             new_allocation: Dict[str, float],
                             risk_metrics: Dict[str, float]) -> str:
        """
        Crea un resumen del rebalanceo realizado.
        
        Args:
            executed_trades: Lista de operaciones ejecutadas
            new_allocation: Nueva asignación del portafolio
            risk_metrics: Métricas de riesgo calculadas
            
        Returns:
            str: Mensaje con el resumen del rebalanceo
        """
        successful_sells = [t for t in executed_trades if t['type'] == 'SELL' and t.get('success', False)]
        successful_buys = [t for t in executed_trades if t['type'] == 'BUY' and t.get('success', False)]
        failed_trades = [t for t in executed_trades if not t.get('success', False)]
        
        total_sold = sum([t.get('value', 0) for t in successful_sells])
        total_bought = sum([t.get('value', 0) for t in successful_buys])
        
        # Crear mensaje - usando emojis texto plano para evitar problemas de formato
        message = "\ud83d\udcca REBALANCEO DE PORTAFOLIO COMPLETADO\n\n"
        
        # Resumen de operaciones
        message += f"Operaciones realizadas: {len(successful_sells) + len(successful_buys)}/{len(executed_trades)}\n"
        message += f"Valor vendido: ${total_sold:.2f}\n"
        message += f"Valor comprado: ${total_bought:.2f}\n\n"
        
        # Detalle de transacciones
        if successful_sells:
            message += "\ud83d\udcb5 Ventas realizadas:\n"
            for trade in successful_sells:
                message += f"  - {trade['symbol']}: {trade['executed_qty']:.4f} a ${trade['executed_price']:.4f} = ${trade['value']:.2f}\n"
            message += "\n"
        
        if successful_buys:
            message += "\ud83d\udcb0 Compras realizadas:\n"
            for trade in successful_buys:
                message += f"  - {trade['symbol']}: {trade['executed_qty']:.4f} a ${trade['executed_price']:.4f} = ${trade['value']:.2f}\n"
            message += "\n"
        
        if failed_trades:
            message += "\u274c Operaciones fallidas:\n"
            for trade in failed_trades:
                message += f"  - {trade['type']} {trade['symbol']}: {trade.get('error', 'Error desconocido')}\n"
            message += "\n"
        
        # Nueva asignación
        message += "\ud83d\udcc8 Nueva asignación de portafolio:\n"
        sorted_allocation = sorted(new_allocation.items(), key=lambda x: x[1], reverse=True)
        for symbol, weight in sorted_allocation:
            if weight >= 0.01:  # Solo mostrar asignaciones significativas
                message += f"  - {symbol}: {weight*100:.1f}%\n"
        
        # Métricas de riesgo
        message += f"\n\u2139\ufe0f Métricas de riesgo:\n"
        message += f"  - Retorno anual esperado: {risk_metrics['annual_return']*100:.1f}%\n"
        message += f"  - Volatilidad anual: {risk_metrics['annual_volatility']*100:.1f}%\n"
        message += f"  - Ratio de Sharpe: {risk_metrics['sharpe_ratio']:.2f}\n"
        message += f"  - Drawdown máximo: {risk_metrics['max_drawdown']*100:.1f}%\n"
        
        return message
    
    def send_rebalance_summary(self, 
                             executed_trades: List[Dict], 
                             new_allocation: Dict[str, float],
                             risk_metrics: Dict[str, float]) -> bool:
        """
        Envía un resumen del rebalanceo realizado.
        
        Args:
            executed_trades: Lista de operaciones ejecutadas
            new_allocation: Nueva asignación del portafolio
            risk_metrics: Métricas de riesgo calculadas
            
        Returns:
            bool: True si la notificación se envía correctamente
        """
        try:
            message = self.create_rebalance_summary(
                executed_trades=executed_trades,
                new_allocation=new_allocation,
                risk_metrics=risk_metrics
            )
            
            # Enviar notificación
            return self.telegram_notifier.send_message(message)
            
        except Exception as e:
            logger.error(f"Error enviando resumen de rebalanceo: {e}")
            return False
    
    def send_allocation_update(self, allocation: Dict[str, float], total_value: float) -> bool:
        """
        Envía una actualización del estado actual del portafolio.
        
        Args:
            allocation: Asignación actual del portafolio
            total_value: Valor total del portafolio en USDC
            
        Returns:
            bool: True si la notificación se envía correctamente
        """
        try:
            message = f"\ud83d\udcb0 ESTADO ACTUAL DEL PORTAFOLIO\n\n"
            message += f"Valor total: ${total_value:.2f}\n\n"
            
            # Asignación actual
            message += "Asignación:\n"
            sorted_allocation = sorted(allocation.items(), key=lambda x: x[1], reverse=True)
            for symbol, weight in sorted_allocation:
                if weight >= 0.01:  # Solo mostrar asignaciones significativas
                    value = total_value * weight
                    message += f"  - {symbol}: {weight*100:.1f}% (${value:.2f})\n"
            
            # Enviar notificación
            return self.telegram_notifier.send_message(message)
            
        except Exception as e:
            logger.error(f"Error enviando actualización de asignación: {e}")
            return False
    
    def send_error(self, message: str) -> bool:
        """
        Envía una notificación de error.
        
        Args:
            message: Mensaje de error
            
        Returns:
            bool: True si la notificación se envía correctamente
        """
        try:
            error_message = f"\u26a0\ufe0f ERROR EN PORTAFOLIO\n\n{message}"
            return self.telegram_notifier.send_message(error_message)
            
        except Exception as e:
            logger.error(f"Error enviando notificación de error: {e}")
            return False
