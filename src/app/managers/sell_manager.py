import time
from typing import List, Dict, Any
from prettytable import PrettyTable

from domain.ports import TradeDataProvider, TradeExecutorPort, SellUseCase
from app.analyzers.sentiment_analyzer import SentimentAnalyzer
from utils.logger import setup_logger
from app.services.price_calculator import PriceCalculator
from app.services.sell_decision_engine import SellDecisionEngine
from config.settings import settings
from app.utils.bubble_registry import get_and_clear_all, register as bubble_register

logging = setup_logger()

class SellManager(SellUseCase):
    """
    Gestor encargado de analizar y ejecutar ventas de criptomonedas.
    """

    def __init__(
        self,
        data_provider: TradeDataProvider,
        executor: TradeExecutorPort,
        sentiment_analyzer: SentimentAnalyzer,
        price_calculator: PriceCalculator,
        decision_engine: SellDecisionEngine,
        profit_margin: float = settings.PROFIT_MARGIN,
        stop_loss_margin: float = settings.STOP_LOSS_MARGIN,
        min_trade_usd: float = settings.MIN_TRADE_USD
    ):
        self.data_provider = data_provider
        self.executor = executor
        self.sentiment_analyzer = sentiment_analyzer
        self.price_calculator = price_calculator
        self.decision_engine = decision_engine
        self.profit_margin = profit_margin
        self.stop_loss_margin = stop_loss_margin
        self.min_trade_usd = min_trade_usd
        # Estado para trailing stop: máximo precio alcanzado por símbolo
        self.trailing_highs: Dict[str, float] = {}

    def show_portfolio(self, balances: List[Dict[str, Any]]) -> None:
        """
        Muestra el resumen del portafolio en una tabla.

        :param balances: Lista de balances de activos.
        """
        table = PrettyTable(["Activo", "Unidades disponibles"])

        for balance in balances:
            table.add_row([balance['asset'], balance['free']])

        print(f"{table}\n")

    def calculate_target_price(
        self, buy_price: float, buy_fee: float, sell_fee: float, quantity: float, profit_margin: float
    ) -> float:
        """
        Calcula el precio objetivo necesario para cubrir comisiones y alcanzar un margen de beneficio.

        :param buy_price: Precio de compra por unidad.
        :param buy_fee: Comisión de compra (e.g., 0.001 para 0.1%).
        :param sell_fee: Comisión de venta (e.g., 0.001 para 0.1%).
        :param quantity: Cantidad de criptomoneda comprada.
        :param profit_margin: Margen de beneficio deseado en porcentaje.
        :return: Precio objetivo por unidad.
        """
        total_cost = (buy_price * quantity) * (1 + buy_fee)
        target_price = (total_cost * (1 + profit_margin / 100)) / (quantity * (1 - sell_fee))
        return target_price

    def _get_average_buy_price(
        self, buy_orders: List[Dict[str, Any]], sell_orders: List[Dict[str, Any]], real_balance: float
    ) -> float:
        """
        Calcula el precio promedio de compra considerando las órdenes de compra y venta.

        :param buy_orders: Lista de órdenes de compra.
        :param sell_orders: Lista de órdenes de venta.
        :param real_balance: Saldo real después de compras y ventas.
        :return: Precio promedio de compra.
        """
        total_bought = sum(float(order['executedQty']) for order in buy_orders)
        total_sold = sum(float(order['executedQty']) for order in sell_orders)
        real_balance = total_bought - total_sold

        valid_buy_orders = []
        for order in buy_orders:
            qty = float(order['executedQty'])
            if qty > 0:
                price = float(order['price']) if float(order['price']) > 0 else float(order['cummulativeQuoteQty']) / qty
                valid_buy_orders.append({'qty': qty, 'price': price})

        if valid_buy_orders and real_balance > 0:
            last_buy_order = valid_buy_orders[-1]
            if real_balance == last_buy_order['qty']:
                return last_buy_order['price']
            else:
                total_spent = sum(order['qty'] * order['price'] for order in valid_buy_orders)
                return total_spent / total_bought if total_bought > 0 else 0.0
        elif len(valid_buy_orders) == 1:
            return valid_buy_orders[0]['price']
        else:
            total_spent = sum(order['qty'] * order['price'] for order in valid_buy_orders)
            return total_spent / total_bought if total_bought > 0 else 0.0

    def analyze_and_execute_sells(self) -> None:
        """
        Analiza la cartera para determinar si es un buen momento para vender criptomonedas y ejecuta las ventas.
        """
        balances = self.data_provider.get_balance_summary()
        usdc_balance = float(next((item['free'] for item in balances if item['asset'] == 'USDC'), 0.0))
        assets = [balance for balance in balances if balance['asset'] != 'USDC' and float(balance['free']) > 1]
        sorted_assets = sorted(assets, key=lambda x: float(x['free']), reverse=True)

        self.show_portfolio(sorted_assets)
        # Obtener y limpiar símbolos marcados para venta rápida por burbuja (registro global)
        quick_syms = get_and_clear_all()

        for asset in sorted_assets:
            try:
                symbol = f"{asset['asset']}USDC"
                asset_orders = self.data_provider.get_all_orders(symbol)
                if symbol in quick_syms:
                    current_price = float(self.data_provider.get_price(symbol))
                    real_balance = float(asset['free'])
                    buy_orders = [o for o in asset_orders if o['side'] == 'BUY']
                    # Calcular precio de compra: usar el más alto de las compras (peor caso) o la última
                    buy_prices = []
                    for o in buy_orders:
                        qty = float(o.get('executedQty', 0))
                        price = float(o.get('price', 0)) if float(o.get('price', 0)) > 0 else (float(o.get('cummulativeQuoteQty', 0)) / qty if qty else 0)
                        if price > 0:
                            buy_prices.append(price)
                    if not buy_prices:
                        logging.warning(f"No hay precios de compra válidos para {symbol} en quick_syms.")
                        bubble_register(symbol)
                        continue
                    # Para evitar ganancias infladas, usamos el precio máximo pagado (worst-case)
                    purchase_price = max(buy_prices)
                    percentage_gain = ((current_price - purchase_price) / purchase_price) * 100
                    threshold = 2.0  # % de beneficio mínimo para venta rápida por burbuja
                    if percentage_gain >= threshold:
                        logging.info(f"Venta rápida por bubble_override para {symbol} con ganancia {percentage_gain:.2f}% >= {threshold}%.")
                        try:
                            trade_result = self.executor.execute_trade(
                                side="SELL",
                                symbol=symbol,
                                order_type="MARKET",
                                positions=real_balance,
                                reason="BUBBLE_QUICK_SELL",
                                percentage_gain=percentage_gain
                            )
                            if trade_result:
                                logging.info(f"Orden de venta rápida por burbuja ejecutada para {symbol}.\n")
                            else:
                                logging.error(f"Orden de venta rápida por burbuja fallida para {symbol}.\n")
                        except Exception as e:
                            logging.error(f"Error al ejecutar venta rápida por burbuja para {symbol}: {e}")
                    else:
                        logging.info(f"[{symbol}] Ganancia {percentage_gain:.2f}% inferior a umbral rápido por burbuja {threshold}%, reintentando más tarde.")
                        bubble_register(symbol)
                    continue

                if not asset_orders:
                    logging.info(f"No se encontraron órdenes para {symbol}.")
                    continue

                buy_orders = [o for o in asset_orders if o['side'] == 'BUY']
                sell_orders = [o for o in asset_orders if o['side'] == 'SELL']
                real_balance = float(asset['free'])

                if real_balance <= 0:
                    logging.debug(f"Saldo real para {symbol} es {real_balance}, omitiendo.")
                    continue

                average_buy_price = self._get_average_buy_price(buy_orders, sell_orders, real_balance)
                if average_buy_price == 0.0:
                    logging.warning(f"No se pudo calcular el precio promedio de compra para {symbol}.")
                    continue

                target_price = self.calculate_target_price(
                    buy_price=average_buy_price,
                    buy_fee=0.001,
                    sell_fee=0.001,
                    quantity=real_balance,
                    profit_margin=self.profit_margin
                )
                current_price = self.data_provider.get_price(symbol)

                # Actualizar máximo histórico intra-trade para trailing stop
                prev_high = self.trailing_highs.get(symbol, average_buy_price)
                self.trailing_highs[symbol] = max(prev_high, current_price)
                trailing_stop_price = self.trailing_highs[symbol] * (1 - (self.stop_loss_margin / 100))
                stop_loss_price = trailing_stop_price

                # Calcular porcentaje de ganancia o pérdida
                percentage_gain = ((current_price - average_buy_price) / average_buy_price) * 100
                percentage_loss = ((average_buy_price - current_price) / average_buy_price) * 100

                logging.info(f"Asset: {asset['asset']}")
                logging.info(f"Precio Actual: ${current_price:,.8f}")
                logging.info(f"Posiciones abiertas: {real_balance:,.2f}")
                logging.info(f"Precio máximo alcanzado: {self.trailing_highs[symbol]:.8f}")
                logging.info(f"Precio Promedio de Compra: ${average_buy_price:,.8f}")
                logging.info(f"Precio Objetivo de Venta: ${target_price:,.8f}")
                logging.info(f"Precio de Stop Loss: ${stop_loss_price:,.8f}")
                logging.info(f"Porcentaje de Ganancia: {percentage_gain:.2f}%\n")
                # logging.info(f"Porcentaje de Pérdida: {percentage_loss:.2f}%")

                if current_price * real_balance < self.min_trade_usd:
                    logging.info(f"Operación menor a mínimo {self.min_trade_usd} USD, omitiendo.")
                    continue
                decision = self.decision_engine.decide(asset, average_buy_price, current_price, real_balance)
                # Evitar ventas por target si la ganancia neta es inferior al umbral configurado
                if decision == "vender ganancia" and percentage_gain < self.profit_margin:
                    logging.info(f"[{symbol}] Ganancia {percentage_gain:.2f}% menor al objetivo {self.profit_margin}%, omitiendo venta para cubrir comisiones.")
                    continue
                if decision != "mantener":
                    self._make_action(decision, symbol, average_buy_price, current_price, real_balance, percentage_gain, percentage_loss)

                # Opcional: espera entre cada operación para evitar sobrecargar la API
                time.sleep(2)

            except Exception as e:
                logging.error(f"Error al procesar la venta para {symbol}: {e}")
    
    def _make_action(self, action, symbol, average_buy_price, current_price, real_balance, percentage_gain, percentage_loss):
        if action == "vender pérdida":
            percentage_loss = ((average_buy_price - current_price) / average_buy_price) * 100
            logging.info(f"Stop loss alcanzado. Vender para limitar pérdidas. -{percentage_loss:,.2f}%.\n")

            try:
                trade_result = self.executor.execute_trade(
                    side="SELL",
                    symbol=symbol,
                    order_type="MARKET",
                    positions=real_balance,
                    reason="STOP_LOSS",
                    percentage_gain=-percentage_loss
                )
                if trade_result:
                    logging.info(f"Orden de venta por stop loss ejecutada para {symbol}.\n")
                else:
                    logging.error(f"Orden de venta por stop loss no se ha podido ejecutar para {symbol}.\n")
            except Exception as e:
                logging.error(f"Error al ejecutar la venta por stop loss para {symbol}: {e}")
        elif action == "vender ganancia":
            logging.info(f"Objetivo de ganancia alcanzado. Vender para asegurar ganancias. +{percentage_gain:,.2f}%.\n")

            try:
                trade_result = self.executor.execute_trade(
                    side="SELL",
                    symbol=symbol,
                    order_type="MARKET",
                    positions=real_balance,
                    reason="PROFIT_TARGET",
                    percentage_gain=percentage_gain
                )
                if trade_result:
                    logging.info(f"Orden de venta por objetivo de ganancia ejecutada para {symbol}.\n")
                else:
                    logging.error(f"Orden de venta por objetivo de ganancia no se ha podido ejecutar para {symbol}.\n")
            except Exception as e:
                logging.error(f"Error al ejecutar la venta por objetivo de ganancia para {symbol}: {e}")
