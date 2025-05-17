import requests
from typing import Optional
from datetime import datetime
from config.telegram import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from loguru import logger

class TelegramNotifier:
    def __init__(self):
        """
        Initializes the Telegram bot for sending notifications.
        """
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.api_url_send = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Sends a text message via Telegram.

        :param message: Message to send.
        :param parse_mode: Message format (e.g., "Markdown").
        :return: True if successfully sent, False otherwise.
        """
        data = {"chat_id": self.chat_id, "text": message, "parse_mode": parse_mode}

        try:
            response = requests.post(self.api_url_send, data=data)
            if response.status_code == 200:
                logger.info(f"[Telegram] Message sent: {message[:50]}...")
                return True
            else:
                logger.error(
                    f"[Telegram] Error sending message: {response.status_code}, {response.text}"
                )
                return False
        except requests.RequestException as e:
            logger.exception(f"[Telegram] Exception sending message: {e}")
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
        Sends a specific buy or sell notification.

        :param side: "BUY" or "SELL".
        :param symbol: Asset symbol (e.g., BTCUSDC).
        :param quantity: Traded quantity.
        :param price: Trade price.
        :param initial_balance: Available balance after trade.
        :param percentage_gain: Profit or loss percentage in case of a sale (optional).
        :param reason: Reason for the trade (e.g., "PROFIT_TARGET", "STOP_LOSS").
        :return: True if successfully sent, False otherwise.
        """
        try:
            message = self._build_trade_message(
                side, symbol, quantity, price, initial_balance, percentage_gain, reason
            )
            return self.send_message(message)
        except ValueError as e:
            logger.error(f"[Telegram] Error generating notification message: {e}")
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
        Builds the notification message for buy or sell operations.

        :param side: "BUY" or "SELL".
        :param symbol: Asset symbol.
        :param quantity: Traded quantity.
        :param price: Trade price.
        :param initial_balance: Available balance after trade.
        :param percentage_gain: Profit or loss percentage in case of a sale.
        :param reason: Reason for the trade (e.g., "PROFIT_TARGET", "STOP_LOSS").
        :return: Formatted message.
        """
        header = "🟢 *BUY EXECUTED*" if side.upper() == "BUY" else "🔴 *SELL EXECUTED*"
        emoji_reason = {
            "STOP_LOSS": "🚨 *STOP LOSS TRIGGERED* 🚨",
            "PROFIT_TARGET": "🎯 *PROFIT TARGET REACHED* 🎯",
            "BUBBLE_QUICK_SELL": "💥 *BUBBLE QUICK SELL EXECUTED* 💥",
        }
        reason_text = emoji_reason.get(reason, header)

        base_message = (
            f"{reason_text}\n"
            f"🔹 *Asset:* `{symbol}`\n"
            f"🔹 *Quantity:* `{quantity:.2f}` units\n"
            f"🔹 *Price:* `${price:,.6f}`\n"
            f"🔹 *Total:* `${quantity * price:,.2f}`\n"
            f"💵 *Balance:* `${initial_balance:,.2f}`\n"
        )

        if side.upper() == "SELL":
            if reason == "STOP_LOSS":
                base_message += (
                    f"🔻 *Loss:* `{percentage_gain:.2f}%`\n"
                    f"⚠️ _Stop loss strategy applied._"
                )
            elif reason == "PROFIT_TARGET":
                base_message += (
                    f"🟢 *Profit:* `{percentage_gain:.2f}%`\n"
                    f"💰 _Profit secured._"
                )
            elif reason == "BUBBLE_QUICK_SELL":
                base_message += (
                    f"📉 *Quick Sell:* `{percentage_gain:.2f}%`\n"
                    f"💥 _Bubble quick sell executed._"
                )
            else:
                base_message += (
                    f"🔵 *Benefits:* `{percentage_gain:.2f}%`\n"
                    f"📊 _Trade completed._"
                )
        elif side.upper() == "BUY":
            base_message += "📈 _Hoping for an increase soon! 🚀_"

        # Message footer
        footer = (
            "\n📅 *Date and time:* "
            f"`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
            "🔔 _Automatically generated notification._"
        )
        return base_message + footer
