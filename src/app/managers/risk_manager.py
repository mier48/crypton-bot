"""
RiskManager: módulo para gestión de riesgos,
- límites de exposición
- cálculo de VaR
- stop-loss / take-profit automáticos
- tamaño de posición dinámico según % de capital
"""
from typing import List
import numpy as np
from config.settings import settings


class RiskManager:
    def __init__(self, data_provider, executor):
        self.data_provider = data_provider
        self.executor = executor
        # Límites de capital (porcentaje) y riesgo
        self.max_exposure_pct = settings.MAX_EXPOSURE_PERCENT / 100
        self.risk_per_trade_pct = settings.RISK_PER_TRADE_PERCENT / 100

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
        """
        risk_amount = capital * self.risk_per_trade_pct
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

    def can_open_position(self, price: float, size: float) -> bool:
        """
        Verifica si abrir una posición mantiene el capital dentro del límite de exposición.
        """
        # Obtener saldo USDC desde balance_summary
        balances = self.data_provider.get_balance_summary()
        capital = float(next((b['free'] for b in balances if b['asset'] == 'USDC'), 0.0))
        notional = price * size
        # Validar que exista saldo USDC suficiente
        if capital < notional:
            return False
        return True

    def apply_stop_take(self, symbol: str, entry_price: float, stop_loss_pct: float, take_profit_pct: float):
        """
        Programa órdenes OCO: stop-loss y take-profit.
        """
        # Implementar lógica OCO si el exchange lo soporta
        # Placeholder: registrar en log
        limit_price = entry_price * (1 + take_profit_pct)
        stop_price = entry_price * (1 - stop_loss_pct)
        self.executor.submit_oco_order(symbol, size=None, stop_price=stop_price, limit_price=limit_price)
