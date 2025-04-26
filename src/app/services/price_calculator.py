from typing import List, Dict, Any
from typing import Tuple
from config.settings import settings

class PriceCalculator:
    """
    Calcula el precio promedio de compra a partir de órdenes.
    """
    def get_average_buy_price(
        self,
        buy_orders: List[Dict[str, Any]],
        sell_orders: List[Dict[str, Any]]
    ) -> float:
        total_bought = sum(float(order.get('executedQty', 0)) for order in buy_orders)
        total_sold = sum(float(order.get('executedQty', 0)) for order in sell_orders)
        real_balance = total_bought - total_sold

        valid_buy_orders = []
        for order in buy_orders:
            qty = float(order.get('executedQty', 0))
            if qty <= 0:
                continue
            price = float(order.get('price', 0)) if float(order.get('price', 0)) > 0 else (
                float(order.get('cummulativeQuoteQty', 0)) / qty if qty else 0
            )
            valid_buy_orders.append({'qty': qty, 'price': price})

        if not valid_buy_orders or real_balance <= 0:
            return 0.0

        last_buy = valid_buy_orders[-1]
        if real_balance == last_buy['qty']:
            return last_buy['price']

        total_spent = sum(o['qty'] * o['price'] for o in valid_buy_orders)
        return total_spent / total_bought if total_bought > 0 else 0.0

    def calculate_prices(self, average_buy_price: float, real_balance: float) -> Tuple[float, float]:
        """
        Calcula el precio objetivo y stop loss basados en los márgenes configurados en settings.
        :return: (target_price, stop_loss_price)
        """
        profit_margin = settings.PROFIT_MARGIN
        stop_loss_margin = settings.STOP_LOSS_MARGIN
        target_price = average_buy_price * (1 + profit_margin / 100)
        stop_loss_price = average_buy_price * (1 - stop_loss_margin / 100)
        return target_price, stop_loss_price
