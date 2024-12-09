import requests
from typing import Optional
from utils.logger import setup_logger
from config.telegram import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = setup_logger(__name__)

class TelegramNotifier:
    def __init__(self):
        """
        Inicializa el bot de Telegram para enviar notificaciones.
        """
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.api_url_send = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Envía un mensaje de texto a través de Telegram.

        :param message: Mensaje a enviar.
        :param parse_mode: Formato del mensaje (e.g., "Markdown").
        :return: True si se envió correctamente, False de lo contrario.
        """
        data = {"chat_id": self.chat_id, "text": message, "parse_mode": parse_mode}

        try:
            response = requests.post(self.api_url_send, data=data)
            if response.status_code == 200:
                logger.info(f"[Telegram] Mensaje enviado: {message[:50]}...")
                return True
            else:
                logger.error(
                    f"[Telegram] Error al enviar mensaje: {response.status_code}, {response.text}"
                )
                return False
        except requests.RequestException as e:
            logger.exception(f"[Telegram] Excepción al enviar mensaje: {e}")
            return False

    def notify_trade(
        self,
        side: str,
        symbol: str,
        quantity: float,
        price: float,
        initial_balance: float,
        percentage_gain: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Envía una notificación específica de compra o venta.

        :param side: "BUY" o "SELL".
        :param symbol: Símbolo del activo (e.g., BTCUSDT).
        :param quantity: Cantidad operada.
        :param price: Precio de la operación.
        :param initial_balance: Balance disponible tras la operación.
        :param percentage_gain: Porcentaje de ganancia o pérdida en caso de venta (opcional).
        :param reason: Motivo de la operación (e.g., "PROFIT_TARGET", "STOP_LOSS").
        :return: True si se envió correctamente, False de lo contrario.
        """
        try:
            message = self._build_trade_message(
                side, symbol, quantity, price, initial_balance, percentage_gain, reason
            )
            return self.send_message(message)
        except ValueError as e:
            logger.error(f"[Telegram] Error al generar mensaje de notificación: {e}")
            return False

    def _build_trade_message(
        self,
        side: str,
        symbol: str,
        quantity: float,
        price: float,
        initial_balance: float,
        percentage_gain: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> str:
        """
        Construye el mensaje de notificación para operaciones de compra o venta.

        :param side: "BUY" o "SELL".
        :param symbol: Símbolo del activo.
        :param quantity: Cantidad operada.
        :param price: Precio de la operación.
        :param initial_balance: Balance disponible tras la operación.
        :param percentage_gain: Porcentaje de ganancia o pérdida en caso de venta.
        :param reason: Motivo de la operación (e.g., "PROFIT_TARGET", "STOP_LOSS").
        :return: Mensaje formateado.
        """
        if side.upper() == "BUY":
            return (
                f"🟢 *COMPRA EJECUTADA*\n"
                f"🔹 *Activo:* {symbol}\n"
                f"🔹 *Cantidad comprada:* {quantity:.6f} unidades\n"
                f"🔹 *Precio de compra:* ${price:.6f}\n"
                f"🔹 *Total invertido:* ${quantity * price:.2f}\n"
                f"💵 *Balance restante:* ${initial_balance:.2f}\n"
                f"\n📈 ¡Esperamos que suba pronto! 🚀"
            )
        elif side.upper() == "SELL":
            if reason == "STOP_LOSS":
                return (
                    f"🚨 *STOP LOSS ACTIVADO* 🚨\n"
                    f"🔹 *Activo:* {symbol}\n"
                    f"🔹 *Cantidad vendida:* {quantity:.2f} unidades\n"
                    f"🔹 *Precio de venta:* ${price:,.6f}\n"
                    f"🔹 *Total vendido:* ${quantity * price:,.2f}\n"
                    f"🔹 *Pérdida:* {percentage_gain:.2f}%\n"
                    f"💵 *Balance actual:* ${initial_balance:,.2f}\n"
                    f"\n⚠️ Se ha limitado la pérdida según la estrategia de stop loss."
                )
            elif reason == "PROFIT_TARGET":
                return (
                    f"🎯 *OBJETIVO DE GANANCIA ALCANZADO* 🎯\n"
                    f"🔹 *Activo:* {symbol}\n"
                    f"🔹 *Cantidad vendida:* {quantity:.2f} unidades\n"
                    f"🔹 *Precio de venta:* ${price:,.6f}\n"
                    f"🔹 *Total vendido:* ${quantity * price:,.2f}\n"
                    f"🔹 *Ganancia:* {percentage_gain:.2f}%\n"
                    f"💵 *Balance actual:* ${initial_balance:,.2f}\n"
                    f"\n💰 ¡Ganancia asegurada! 🎉"
                )
            else:
                return (
                    f"🔴 *VENTA EJECUTADA*\n"
                    f"🔹 *Activo:* {symbol}\n"
                    f"🔹 *Cantidad vendida:* {quantity:.2f} unidades\n"
                    f"🔹 *Precio de venta:* ${price:,.6f}\n"
                    f"🔹 *Total vendido:* ${quantity * price:,.2f}\n"
                    f"🔹 *Beneficios:* {percentage_gain:.2f}%\n"
                    f"💵 *Balance actual:* ${initial_balance:,.2f}\n"
                    f"\n💰 ¡Operación ejecutada! 🎉"
                )
        else:
            raise ValueError(f"Dirección inválida para la operación: {side}")
