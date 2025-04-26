from typing import Dict, Any
import logging
from app.services.base_decision_engine import BaseDecisionEngine
from app.services.price_calculator import PriceCalculator
from config.settings import settings

logger = logging.getLogger(__name__)

class SellDecisionEngine(BaseDecisionEngine):
    """
    Motor de decisión para ventas usando OpenAI o reglas internas.
    """
    def __init__(
        self,
        openai_client,
        sentiment_analyzer,
        coin_gecko_client,
        price_calculator: PriceCalculator
    ) -> None:
        super().__init__(openai_client, sentiment_analyzer, coin_gecko_client)
        self.price_calculator = price_calculator
        self.use_open_ai = settings.USE_OPEN_AI_API
        # Estado para trailing stop: máximo precio alcanzado por símbolo
        self.trailing_highs: Dict[str, float] = {}
        # Márgenes para decisión
        self.stop_loss_margin = settings.STOP_LOSS_MARGIN
        self.profit_margin = settings.PROFIT_MARGIN

    def decide(
        self,
        asset: Dict[str, Any],
        average_buy_price: float,
        current_price: float,
        real_balance: float
    ) -> str:
        """
        Devuelve 'vender ganancia', 'vender pérdida' o 'mantener'.
        """
        # Calcular porcentajes
        percentage_gain = ((current_price - average_buy_price) / average_buy_price) * 100
        # calcular precios base
        target_price, _ = self.price_calculator.calculate_prices(
            average_buy_price,
            real_balance
        )
        # Actualizar trailing stop
        symbol = f"{asset['asset']}USDC"
        prev_high = self.trailing_highs.get(symbol, average_buy_price)
        high = max(prev_high, current_price)
        self.trailing_highs[symbol] = high
        trailing_stop = high * (1 - self.stop_loss_margin / 100)

        # Decisión sin OpenAI
        if not self.use_open_ai:
            if current_price <= trailing_stop:
                logger.debug(f"[{symbol}] Trailing stop alcanzado: {current_price} <= {trailing_stop}")
                return "vender pérdida"
            if current_price >= target_price and percentage_gain >= self.profit_margin:
                logger.debug(f"[{symbol}] Objetivo de ganancia alcanzado: {percentage_gain:.2f}% >= {self.profit_margin}%")
                return "vender ganancia"
            return "mantener"

        # Decisión con OpenAI
        symbol = f"{asset['asset']}USDC"
        sentiment, news_info = self.get_sentiment_and_news(symbol)

        prompt = (
            "Eres un experto en trading y análisis de criptomonedas.\n\n"
            "### Datos Actuales\n"
            f"- Activo: {symbol}\n"
            f"- Precio de Compra Promedio: ${average_buy_price:,.6f}\n"
            f"- Precio Actual: ${current_price:,.6f}\n"
            f"- Cantidad Disponible: {real_balance:,.6f}\n\n"
            "### Indicadores de Rendimiento\n"
            f"- Porcentaje de Ganancia: {percentage_gain:.2f}%\n"
            f"- Precio Objetivo de Venta: ${target_price:,.6f}\n"
            f"- Precio de Stop Loss: ${trailing_stop:,.6f}\n\n"
            f"### Sentimiento del Mercado: {sentiment:.2f}\n\n"
            f"### Noticias Relevantes:\n{news_info}\n\n"
            "### Pregunta\n"
            "¿Recomiendas 'Vender Ganancia', 'Vender Pérdida' o 'Mantener'? "
            "Responde solo una de esas opciones, sin explicaciones."
        )
        response = self.send_openai_prompt(prompt)
        if not response:
            return "mantener"
        resp = response.lower()
        if "vender ganancia" in resp:
            return "vender ganancia"
        if "vender pérdida" in resp or "vender perdida" in resp:
            return "vender pérdida"
        return "mantener"
