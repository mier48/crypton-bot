from typing import Optional, Dict, TypedDict
from api.binance.data_manager import BinanceDataManager
from utils.logger import setup_logger
from app.notifiers.telegram_notifier import TelegramNotifier
from app.validator import get_decimals_for_symbol

logger = setup_logger(__name__)

class Order(TypedDict):
    fills: list[Dict[str, str]]
    executedQty: str

class TradeExecutor:
    def __init__(self):
        self.notifier = TelegramNotifier()
        self.data_manager = BinanceDataManager()

    def execute_trade(
        self, 
        side: str, 
        symbol: str, 
        order_type: str, 
        positions: float, 
        reason: Optional[str] = None,
        price: Optional[float] = None, 
        percentage_gain: Optional[float] = None
    ) -> Optional[bool]:
        """
        Ejecuta una orden de compra o venta en Binance y envía una notificación.

        :param side: Dirección de la operación ("BUY" o "SELL").
        :param symbol: Símbolo de la criptomoneda (e.g., "BTCUSDC").
        :param order_type: Tipo de orden (e.g., "LIMIT", "MARKET").
        :param positions: Cantidad a operar.
        :param reason: Motivo de la operación (e.g., "PROFIT_TARGET", "STOP_LOSS").
        :param price: Precio de la operación (opcional, relevante para órdenes LIMIT).
        :param percentage_gain: Porcentaje de ganancia o pérdida para notificar en ventas (opcional).
        :return: True si la operación fue exitosa, False si hubo un error, None si no se ejecutó.
        """
        try:
            # Validación inicial
            if side not in {"BUY", "SELL"}:
                raise ValueError(f"Dirección inválida: {side}")
            if not symbol or not order_type:
                raise ValueError("El símbolo y el tipo de orden son obligatorios.")
            
            # Obtener datos del símbolo
            symbol_data = self.data_manager.fetch_symbol_data(symbol)
            if not symbol_data:
                raise ValueError(f"No se pudo obtener información para el símbolo {symbol}")

            decimals = get_decimals_for_symbol(symbol_data, symbol)
            if decimals is None:
                raise ValueError(f"No se pudo determinar los decimales permitidos para el símbolo {symbol}")

            # Formatear cantidad
            quantity = self._format_quantity(positions, decimals)

            # Crear orden
            order = self.data_manager.create_order(
                symbol=symbol,
                side=side,
                type_=order_type,
                quantity=quantity,
                price=price
            )
            if not order:
                logger.error("La orden no se pudo ejecutar.")
                return False
            else:
                # Procesar y registrar la orden
                return self._process_order(order, side, symbol, percentage_gain, reason)
        
        except Exception as e:
            logger.exception(f"Error al ejecutar la orden: {e}")
            return False

    def _format_quantity(self, positions: float, decimals: int) -> float:
        """Formatea la cantidad de posiciones según los decimales permitidos."""
        quantity = round(positions, decimals)
        return float(f"{quantity:.1f}") if decimals == 0 else quantity

    def _process_order(
        self, 
        order: Order, 
        side: str, 
        symbol: str, 
        percentage_gain: Optional[float], 
        reason: Optional[str] = None  # Nuevo parámetro
    ) -> bool:
        """
        Procesa la orden ejecutada y envía las notificaciones correspondientes.

        :param order: Datos de la orden ejecutada.
        :param side: Dirección de la operación ("BUY" o "SELL").
        :param symbol: Símbolo de la criptomoneda.
        :param percentage_gain: Porcentaje de ganancia o pérdida (relevante para ventas).
        :param reason: Motivo de la operación (e.g., "PROFIT_TARGET", "STOP_LOSS").
        :return: True si la operación fue procesada correctamente.
        """
        executed_price = float(order["fills"][0]["price"])
        executed_quantity = float(order["executedQty"])

        logger.info(
            f"{side} ejecutado para {symbol}: {executed_quantity} unidades a ${executed_price:,.6f}"
        )

        balances = self.data_manager.get_balance_summary()
        initial_balance = self._get_balance(balances, "USDC")

        self.notifier.notify_trade(
            side, 
            symbol, 
            executed_quantity, 
            executed_price, 
            initial_balance, 
            percentage_gain,
            reason
        )
        return True

    def _get_balance(self, balances: list[Dict[str, str]], asset: str) -> float:
        """Obtiene el balance disponible de un activo específico."""
        return next((float(item['free']) for item in balances if item['asset'] == asset), 0.0)
