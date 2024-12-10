# src/app/notifier.py

import requests
from typing import Optional
from datetime import datetime
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
        header = "🟢 *COMPRA EJECUTADA*" if side.upper() == "BUY" else "🔴 *VENTA EJECUTADA*"
        emoji_reason = {
            "STOP_LOSS": "🚨 *STOP LOSS ACTIVADO* 🚨",
            "PROFIT_TARGET": "🎯 *OBJETIVO DE GANANCIA ALCANZADO* 🎯",
        }
        reason_text = emoji_reason.get(reason, header)

        base_message = (
            f"{reason_text}\n"
            f"🔹 *Activo:* `{symbol}`\n"
            f"🔹 *Cantidad:* `{quantity:.2f}` unidades\n"
            f"🔹 *Precio:* `${price:,.6f}`\n"
            f"🔹 *Total:* `${quantity * price:,.2f}`\n"
            f"💵 *Balance:* `${initial_balance:,.2f}`\n"
        )

        if side.upper() == "SELL":
            if reason == "STOP_LOSS":
                base_message += (
                    f"🔻 *Pérdida:* `{percentage_gain:.2f}%`\n"
                    f"⚠️ _Estrategia de stop loss aplicada._"
                )
            elif reason == "PROFIT_TARGET":
                base_message += (
                    f"🟢 *Ganancia:* `{percentage_gain:.2f}%`\n"
                    f"💰 _Ganancia asegurada._"
                )
            else:
                base_message += (
                    f"🔵 *Beneficios:* `{percentage_gain:.2f}%`\n"
                    f"📊 _Operación completada._"
                )
        elif side.upper() == "BUY":
            base_message += "📈 _¡Esperamos que suba pronto! 🚀_"

        # Pie del mensaje
        footer = (
            "\n📅 *Fecha y hora:* "
            f"`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
            "🔔 _Notificación generada automáticamente._"
        )
        return base_message + footer
