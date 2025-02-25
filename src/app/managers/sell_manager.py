import time
from typing import List, Dict, Any
from prettytable import PrettyTable

from api.binance.data_manager import BinanceDataManager
from api.openai.client import OpenAIClient
from api.coingecko.client import CoinGeckoClient
from app.analyzers.sentiment_analyzer import SentimentAnalyzer
from app.executors.trade_executor import TradeExecutor
from utils.logger import setup_logger

logging = setup_logger()

class SellManager:
    """
    Gestor encargado de analizar y ejecutar ventas de criptomonedas.
    """

    def __init__(
        self,
        data_manager: BinanceDataManager,
        executor: TradeExecutor,
        sentiment_analyzer: SentimentAnalyzer,
        coin_gecko_client: CoinGeckoClient,
        openai_client: OpenAIClient,
        profit_margin: float,
        stop_loss_margin: float,
        use_open_ai_api: bool
    ):
        self.data_manager = data_manager
        self.executor = executor
        self.sentiment_analyzer = sentiment_analyzer
        self.coin_gecko_client = coin_gecko_client
        self.openai_client = openai_client
        self.profit_margin = profit_margin
        self.stop_loss_margin = stop_loss_margin
        self.use_open_ai_api = use_open_ai_api

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
        # total_bought = sum(float(order['executedQty']) for order in buy_orders)
        # total_sold = sum(float(order['executedQty']) for order in sell_orders)
        # net_balance = total_bought - total_sold

        # if net_balance <= 0:
        #     logging.debug("No hay balance neto para calcular el precio promedio de compra.")
        #     return 0.0

        # total_spent = sum(float(order['price']) * float(order['executedQty']) for order in buy_orders)
        # average_buy_price = total_spent / net_balance if net_balance > 0 else 0.0
        # return average_buy_price
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
        balances = self.data_manager.get_balance_summary()
        usdt_balance = float(next((item['free'] for item in balances if item['asset'] == 'USDT'), 0.0))
        assets = [balance for balance in balances if balance['asset'] != 'USDT' and float(balance['free']) > 1]
        sorted_assets = sorted(assets, key=lambda x: float(x['free']), reverse=True)

        self.show_portfolio(sorted_assets)

        for asset in sorted_assets:
            try:
                symbol = f"{asset['asset']}USDT"
                asset_orders = self.data_manager.get_all_orders(symbol)

                if not asset_orders:
                    logging.info(f"No se encontraron órdenes para {symbol}.")
                    continue

                buy_orders = [order for order in asset_orders if order['side'] == 'BUY']
                sell_orders = [order for order in asset_orders if order['side'] == 'SELL']
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
                current_price = self.data_manager.get_price(symbol)

                # Calcular el precio de stop loss
                stop_loss_price = average_buy_price * (1 - (self.stop_loss_margin / 100))

                # Calcular porcentaje de ganancia o pérdida
                percentage_gain = ((current_price - average_buy_price) / average_buy_price) * 100
                percentage_loss = ((average_buy_price - current_price) / average_buy_price) * 100

                logging.info(f"Asset: {asset['asset']}")
                logging.info(f"Precio Actual: ${current_price:,.8f}")
                logging.info(f"Posiciones abiertas: {real_balance:,.2f}")
                logging.info(f"Precio Promedio de Compra: ${average_buy_price:,.8f}")
                logging.info(f"Precio Objetivo de Venta: ${target_price:,.8f}")
                logging.info(f"Precio de Stop Loss: ${stop_loss_price:,.8f}")
                logging.info(f"Porcentaje de Ganancia: {percentage_gain:.2f}%")
                # logging.info(f"Porcentaje de Pérdida: {percentage_loss:.2f}%")

                # Verificar si se alcanza el stop loss
                if current_price <= stop_loss_price or current_price >= target_price:
                    if current_price * real_balance < 5: # Verificar si el monto total es menor a $5.00. $5.00 es el mínimo permitido en Binance.
                        logging.info(f"No se puede vender {asset['asset']} por menos de $5.00. Actualmente tienes: ${current_price*real_balance}.\n")
                        continue

                    if self.use_open_ai_api:
                        logging.info(f"Enviando prompt a OpenAI para {symbol}...")
                        self._use_open_ai_api(asset, symbol, average_buy_price, current_price, real_balance, percentage_gain, percentage_loss)
                    else:
                        logging.info("No se enviará el prompt a OpenAI debido a la configuración actual.")
                        if current_price <= stop_loss_price:
                            self._make_action("vender pérdida", symbol, average_buy_price, current_price, real_balance, percentage_gain, percentage_loss)
                        elif current_price >= target_price:
                            self._make_action("vender ganancia", symbol, average_buy_price, current_price, real_balance, percentage_gain, percentage_loss)
                else:
                    logging.info("No hacer nada, estas fuera del stop loss y del margen de ganacia.\n")

                # Opcional: espera entre cada operación para evitar sobrecargar la API
                time.sleep(2)

            except Exception as e:
                logging.error(f"Error al procesar la venta para {symbol}: {e}")
    
    def _use_open_ai_api(self, asset, symbol, average_buy_price, current_price, real_balance, percentage_gain, percentage_loss):
        # Obtener sentimiento y noticias relevantes
        sentiment = self.sentiment_analyzer.get_overall_sentiment(asset['asset'])
        news_info = self.coin_gecko_client.fetch_crypto_news(asset['asset'])

        logging.info(f"El sentimiento general para {asset['asset']} es {sentiment:.2f} (1 positivo, 0 neutro, -1 negativo).")

        # Crear el prompt para OpenAI
        prompt = (
            "Eres un experto en trading y análisis de criptomonedas. Quieres tomar la mejor decisión para tu inversión.\n\n"
            "### Contexto\n"
            "Tienes una posición abierta en el mercado de criptomonedas y el precio ha cambiado.\n\n"
            "### Datos Actuales\n"
            f"- Activo: {symbol}\n"
            f"- Precio de compra promedio: ${average_buy_price:,.6f}\n"
            f"- Precio actual: ${current_price:,.6f}\n"
            f"- Cantidad: {real_balance:,.6f}\n"
            f"- Porcentaje de ganancia: {percentage_gain:.2f}%\n"
            f"- Porcentaje de pérdida: {percentage_loss:.2f}%\n"
            f"- Mi margen de stop loss es de: {self.stop_loss_margin}%\n"
            "### Sentimiento del Mercado\n"
            f"El sentimiento general para {asset['asset']} es {sentiment:.2f} (1 positivo, 0 neutro, -1 negativo).\n\n"
            "### Noticias Relevantes\n"
            f"{news_info}\n\n"
            "### Pregunta\n"
            "¿Recomiendas vender ahora para aprovechar las ganancias, vender para limitar pérdidas o mantener la posición si consideras que puede volver a subir de precio? "
            "Tienes que responder solamente 'Vender Ganancia', 'Vender Pérdida' o 'Mantener'. Muy importante, solo responde una de las 3 opciones anteriores.\n\n"
            "Tu recomendación debe basarse en un análisis riguroso de los datos proporcionados y las condiciones del mercado."
        )

        # Consultar a OpenAI
        response = self.openai_client.send_prompt(prompt)
        
        if response:
            logging.info(f"Respuesta de openAI para {symbol}: {response}")

            response_lower = response.lower()
            if "vender ganancia" in response_lower:
                self._make_action("vender ganancia", symbol, average_buy_price, current_price, real_balance, percentage_gain, percentage_loss)
            elif "vender pérdida" in response_lower:
                self._make_action("vender pérdida", symbol, average_buy_price, current_price, real_balance, percentage_gain, percentage_loss)
            elif "mantener" in response_lower:
                logging.info(f"Decisión de mantener la posición según recomendación de OpenAI para {symbol}.\n")
            else:
                logging.warning(f"Respuesta no reconocida de OpenAI para {symbol}: {response}.\n")
        else:
            logging.warning(f"No se recibió respuesta de OpenAI. Manteniendo la posición por defecto para {symbol}.\n")

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

