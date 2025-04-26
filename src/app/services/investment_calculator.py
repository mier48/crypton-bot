from typing import Optional

class InvestmentCalculator:
    """
    Calcula la cantidad de USDC a invertir según el sentimiento y reglas de gestión de riesgo.
    """
    def __init__(self, min_pct: float = 0.02, max_pct: float = 0.20):
        # Porcentajes mínimo y máximo de asignación de capital
        self.min_pct = min_pct
        self.max_pct = max_pct

    def calculate_size(self, usdc_balance: float, sentiment_score: float) -> float:
        """
        Determina la cantidad a invertir en base al sentimiento (0-10).

        :param usdc_balance: Fondos disponibles en USDC.
        :param sentiment_score: Puntuación de sentimiento de 0 a 10.
        :return: Monto de USDC a invertir.
        """
        # Normalizar sentimiento a 0-1
        score_norm = max(0.0, min(sentiment_score / 10.0, 1.0))
        # Mapear a rango de porcentaje
        pct = self.min_pct + (self.max_pct - self.min_pct) * score_norm
        return round(usdc_balance * pct, 8)
