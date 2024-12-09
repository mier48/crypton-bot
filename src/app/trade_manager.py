# src/app/trade_manager.py

import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple, Optional

from prettytable import PrettyTable
from concurrent.futures import ThreadPoolExecutor, as_completed

from api.binance.data_manager import BinanceDataManager
from app.analyzer import MarketAnalyzer
from app.notifier import TelegramNotifier
from app.trade_executor import TradeExecutor
from utils.logger import setup_logger

from config.default import DEFAULT_PROFIT_MARGIN, DEFAULT_SLEEP_INTERVAL, DEFAULT_INVESTMENT_AMOUNT, DEFAULT_MAX_BUY_PRICE, DEFAULT_STOP_LOSS_MARGIN

logging = setup_logger()

class TradeManager:
    """
    Clase para el análisis de tendencias y automatización de trading en el mercado de criptomonedas utilizando datos de Binance.
    """

    INTERVAL_MAP: Dict[str, int] = {
        "1s": 1_000,
        "1m": 60_000,
        "1h": 3_600_000,
        "1d": 86_400_000,
    }

    _logger_initialized: bool = False  # Variable de clase para rastrear la inicialización del logger

    def __init__(
        self,
        max_records: int = 500,
        profit_margin: float = DEFAULT_PROFIT_MARGIN,
        stop_loss_margin: float = DEFAULT_STOP_LOSS_MARGIN,
        sleep_interval: int = DEFAULT_SLEEP_INTERVAL
    ):
        """
        Inicializa el TradeManager con todos los componentes necesarios.

        :param data_manager: Instancia de BinanceDataManager.
        :param analyzer: Instancia de MarketAnalyzer.
        :param executor: Instancia de TradeExecutor.
        :param notifier: Instancia de TelegramNotifier.
        :param max_records: Número máximo de registros por solicitud.
        :param profit_margin: Margen de beneficio deseado en porcentaje.
        :param sleep_interval: Intervalo de espera entre ciclos de automatización en segundos.
        """
        self.data_manager = BinanceDataManager()
        self.notifier = TelegramNotifier()
        self.executor = TradeExecutor()
        self.max_records = max_records
        self.profit_margin = profit_margin
        self.stop_loss_margin = stop_loss_margin
        self.sleep_interval = sleep_interval
        self.running = False

    def calculate_interval_in_milliseconds(self, interval: str) -> int:
        """
        Calcula la duración de un intervalo en milisegundos.

        :param interval: Intervalo de tiempo (e.g., "1m", "1h").
        :return: Duración en milisegundos.
        :raises ValueError: Si el intervalo no es soportado.
        """
        if interval not in self.INTERVAL_MAP:
            raise ValueError(f"Intervalo '{interval}' no soportado.")
        return self.INTERVAL_MAP[interval]

    def fetch_all_data(
        self, symbol: str, start_time: int, end_time: int, interval: str = "2m"
    ) -> List[List[Any]]:
        """
        Recopila todos los datos históricos para un símbolo dentro de un rango de tiempo.

        :param symbol: Símbolo de la criptomoneda (e.g., "BTCUSDT").
        :param start_time: Tiempo de inicio en milisegundos.
        :param end_time: Tiempo de fin en milisegundos.0.12
        :param interval: Intervalo de tiempo para los datos.
        :return: Lista de datos históricos.
        """
        all_data: List[List[Any]] = []
        interval_ms = self.calculate_interval_in_milliseconds(interval)
        max_time_range = interval_ms * self.max_records

        current_start = start_time
        while current_start < end_time:
            current_end = min(current_start + max_time_range, end_time)

            try:
                data = self.data_manager.fetch_historical_data(
                    symbol, current_start, current_end, interval=interval
                )
                if not data:
                    logging.debug(f"No se obtuvieron datos para {symbol} entre {current_start} y {current_end}.")
                    break

                all_data.extend(data)
                current_start = int(data[-1][6])

                if len(data) < self.max_records:
                    logging.debug(f"Datos insuficientes para continuar: {len(data)} registros obtenidos.")
                    break

                time.sleep(2)  # Respetar límites de la API
            except Exception as e:
                logging.error(f"Error al obtener datos para {symbol}: {e}")
                break

        return all_data

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

    def analyze_and_execute_buys(self) -> None:
        """
        Analiza el mercado para determinar si es un buen momento para comprar criptomonedas y ejecuta las compras.
        """
        categories = {
            "Top 20 Más Populares (precio entre $0.5 y $2.5)": self.data_manager.get_popular_mid_price(30),
            "Top 20 Gainers": self.data_manager.get_top_gainers(30),
            "Top 20 Más Populares (precio entre $0.01 y $0.5)": self.data_manager.get_popular_low_price(30),
            # "Top 20 Más Populares (precio entre $0.00001 y $0.01)": self.data_manager.get_popular_extra_low_price(30)
        }

        now = datetime.now(timezone.utc)
        end_time = int(now.timestamp() * 1000)
        start_time = int((now - timedelta(hours=50)).timestamp() * 1000)

        result: Dict[str, Any] = {}

        def process_coin(coin: Dict[str, Any]) -> Tuple[str, Optional[Any]]:
            """
            Procesa un solo símbolo de moneda para analizar su tendencia.

            :param coin: Diccionario con información de la moneda.
            :return: Tupla con el símbolo y el resultado del análisis.
            """
            symbol = coin.get('symbol')
            last_price = coin.get('lastPrice')
            logging.debug(f"Recopilando datos históricos de {symbol} (${last_price})...")
            try:
                data = self.fetch_all_data(symbol, start_time, end_time, interval="1m")
                logging.debug(f"Se han recopilado {len(data)} datos históricos para {symbol}.")

                if not data:
                    return symbol, None

                analyzer = MarketAnalyzer(data)
                trend = analyzer.analyze()

                return symbol, trend
            except Exception as e:
                logging.error(f"Error procesando {symbol}: {e}")
                return symbol, False

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_symbol = {
                executor.submit(process_coin, coin): coin.get('symbol')
                for category, coins in categories.items()
                for coin in coins
            }

            for future in as_completed(future_to_symbol):
                symbol, trend = future.result()
                if trend:
                    result[symbol] = trend

        logging.info(f"Mostrando {len(result)} recomendaciones de compra.")
        for symbol, trend in result.items():
            if trend:
                quantity_to_buy = self.calculate_quantity_to_buy(symbol)
                if quantity_to_buy > 0:
                    try:
                        current_price = self.data_manager.get_price(symbol)
                        if current_price < DEFAULT_MAX_BUY_PRICE:
                            self.executor.execute_trade(side="BUY", symbol=symbol, order_type="MARKET", positions=quantity_to_buy, price=current_price)
                        else:
                            logging.info(f"El precio de {symbol} es demasiado alto para comprar (${current_price:,.6f}).")

                    except Exception as e:
                        logging.error(f"Error al ejecutar la compra para {symbol}: {e}")

            time.sleep(3)

    def analyze_and_execute_sells(self) -> None:
        """
        Analiza la cartera para determinar si es un buen momento para vender criptomonedas y ejecuta las ventas.
        """
        balances = self.data_manager.get_balance_summary()
        initial_balance = next((item['free'] for item in balances if item['asset'] == 'USDT'), 0.0)
        assets = [balance for balance in balances if float(balance['free']) > 1]
        sorted_assets = sorted(assets, key=lambda x: float(x['free']), reverse=True)

        self.show_portfolio(sorted_assets)

        for asset in sorted_assets:
            if asset['asset'] == 'USDT':
                continue

            symbol = f"{asset['asset']}USDT"
            asset_orders = self.data_manager.get_all_orders(symbol)

            if not asset_orders:
                logging.info(f"No se encontraron órdenes para {symbol}.")
                continue

            buy_orders = sorted(
                [order for order in asset_orders if order['side'] == 'BUY'],
                key=lambda x: x['time']
            )
            sell_orders = sorted(
                [order for order in asset_orders if order['side'] == 'SELL'],
                key=lambda x: x['time']
            )

            real_balance = float(asset['free'])

            if real_balance <= 0:
                logging.debug(f"Saldo real para {symbol} es {real_balance}, omitiendo.")
                continue

            average_buy_price = self._get_average_buy_price(buy_orders, sell_orders, real_balance)
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

            logging.info(f"Asset: {symbol}")
            logging.info(f"Precio Actual: ${current_price:,.6f}")
            logging.info(f"Posiciones abiertas: {real_balance:,.2f}")
            logging.info(f"Precio Promedio de Compra: ${average_buy_price:,.6f}")
            logging.info(f"Precio Objetivo de Venta: ${target_price:,.6f}")
            logging.info(f"Precio de Stop Loss: ${stop_loss_price:,.6f}")
            
            # Determinar y registrar solo el porcentaje relevante
            if current_price > average_buy_price:
                logging.info(f"Porcentaje de Ganancia: {percentage_gain:.2f}%")
            elif current_price < average_buy_price:
                logging.info(f"Porcentaje de Pérdida: {percentage_loss:.2f}%")
            else:
                logging.info("Sin ganancia ni pérdida.")

            # Verificar si se alcanza el stop loss
            if current_price <= stop_loss_price:
                percentage_loss = ((average_buy_price - current_price) / average_buy_price) * 100
                logging.info(f"Stop Loss alcanzado. Vender para limitar pérdidas a {percentage_loss:,.2f}%.\n")
                try:
                    self.executor.execute_trade(
                        side="SELL",
                        symbol=symbol,
                        order_type="MARKET",
                        positions=real_balance,
                        reason="STOP_LOSS",
                        percentage_gain=-percentage_loss  # Nota: porcentaje negativo para pérdida
                    )
                except Exception as e:
                    logging.error(f"Error al ejecutar la venta por stop loss para {symbol}: {e}")
                continue  # Salta al siguiente activo después de ejecutar el stop loss

            # Verificar si se alcanza el objetivo de ganancia
            if current_price < target_price:
                percentage_to_target = ((target_price - current_price) / current_price) * 100
                logging.info(f"No vender, aún debe subir un {percentage_to_target:,.2f}%\n")
            else:
                percentage_gain = ((current_price - average_buy_price) / average_buy_price) * 100
                logging.info(f"Vender, puedes ganar un {percentage_gain:,.2f}%\n")
                try:
                    self.executor.execute_trade(
                        side="SELL", 
                        symbol=symbol, 
                        order_type="MARKET", 
                        positions=real_balance,
                        reason="PROFIT_TARGET",
                        percentage_gain=percentage_gain
                    )
                except Exception as e:
                    logging.error(f"Error al ejecutar la venta para {symbol}: {e}")

    def calculate_quantity_to_buy(self, symbol: str) -> float:
        """
        Calcula la cantidad de criptomoneda a comprar basado en tu lógica de inversión.

        :param symbol: Símbolo de la criptomoneda (e.g., "BTCUSDT").
        :return: Cantidad a comprar.
        """
        # Implementa tu lógica para determinar cuánto comprar.
        # Por ejemplo, podrías decidir invertir un porcentaje fijo de tu saldo en USDT.
        usdt_balance = float(next((item['free'] for item in self.data_manager.get_balance_summary() if item['asset'] == 'USDT'), 0.0))
        if usdt_balance < 5:
            return 0

        investment_amount = DEFAULT_INVESTMENT_AMOUNT
        current_price = self.data_manager.get_price(symbol)
        quantity = investment_amount / current_price if current_price > 0 else 0
        return quantity
    
    def run(self) -> None:
        """
        Inicia el proceso combinado de análisis de tendencias para comprar y automatización de ventas para vender.
        """
        self.running = True
        logging.info("Inicio de la automatización combinada de compras y ventas.")

        while self.running:
            try:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    # Ejecutar análisis de compra
                    buy_future = executor.submit(self.analyze_and_execute_buys)

                    # Ejecutar análisis de venta
                    sell_future = executor.submit(self.analyze_and_execute_sells)

                    # Esperar a que ambas tareas terminen
                    # for future in as_completed([buy_future, sell_future]):
                        # pass  # Las funciones ya manejan sus propias excepciones y logging

                time.sleep(self.sleep_interval)

            except KeyboardInterrupt:
                self.running = False
                logging.info("Automatización combinada detenida por el usuario.")

            except Exception as e:
                logging.error(f"Error en la automatización combinada: {e}")
                self.running = False
