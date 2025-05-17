import time
from typing import List, Dict, Any, Optional
from prettytable import PrettyTable
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from domain.ports import TradeDataProvider, TradeExecutorPort, SellUseCase
from app.analyzers.sentiment_analyzer import SentimentAnalyzer
from app.services.price_calculator import PriceCalculator
from app.services.sell_decision_engine import SellDecisionEngine
from config.settings import settings
from config.database import SQLALCHEMY_DATABASE_URL
from models.asset import Asset
from loguru import logger

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
        
        # Configurar la conexión a la base de datos
        self.engine = create_engine(SQLALCHEMY_DATABASE_URL)
        
    def get_asset_from_db(self, symbol: str) -> Optional[Asset]:
        """
        Obtiene un activo de la base de datos por su símbolo.
        
        Args:
            symbol: Símbolo del activo (ej: 'BTC')
            
        Returns:
            Objeto Asset si se encuentra, None en caso contrario
        """
        with Session(self.engine) as session:
            return session.query(Asset).filter(Asset.symbol == symbol).first()

    def show_portfolio(self, balances: List[Dict[str, Any]]) -> None:
        """
        Muestra el resumen del portafolio en una tabla.

        :param balances: Lista de balances de activos.
        """
        table = PrettyTable(["Activo", "Unidades disponibles"])

        for balance in balances:
            if float(balance['free']) <= 1:
                continue
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
        Analiza la cartera para determinar si es un buen momento para vender criptomonedas
        basándose en los parámetros de la base de datos y ejecuta las ventas.
        """
        balances = self.data_provider.get_balance_summary()
        assets = [balance for balance in balances 
                 if balance['asset'] != 'USDC' and float(balance['free']) > 0]
        
        if not assets:
            logger.info("No hay activos para vender.")
            return
            
        self.show_portfolio(assets)
        
        for asset in assets:
            symbol = asset['asset']
            symbol_pair = f"{symbol}USDC"
            current_balance = float(asset['free'])
            
            try:
                if current_balance <= 1:
                    logger.info(f"No se vende {symbol} por debajo de 1 unidad.")
                    continue

                # Obtener el activo de la base de datos
                db_asset = self.get_asset_from_db(symbol)
                if not db_asset:
                    logger.warning(f"No se encontró el activo {symbol} en la base de datos.")
                    continue
                
                # Obtener el precio actual
                current_price = float(self.data_provider.get_price(symbol_pair))
                if not current_price:
                    logger.warning(f"No se pudo obtener el precio actual para {symbol_pair}")
                    continue
                
                # Calcular ganancia/pérdida porcentual
                purchase_price = db_asset.purchase_price
                percentage_gain = ((current_price - purchase_price) / purchase_price) * 100
                
                # Determinar el umbral de beneficio según los flags
                if db_asset.is_bubble:
                    profit_threshold = 1.0  # 1% para activos marcados como burbuja
                    sell_reason = "BUBBLE_SELL"
                elif db_asset.force_sell:
                    profit_threshold = 0.25  # 0.25% para venta forzada
                    sell_reason = "FORCE_SELL"
                else:
                    profit_threshold = self.profit_margin  # Margen de beneficio por defecto
                    sell_reason = "PROFIT_TAKING"
                
                logger.info(f"Analizando {symbol}: "
                            f"Compra=${purchase_price:.8f} "
                            f"Actual=${current_price:.8f} "
                            f"Ganancia={percentage_gain:.2f}% "
                            f"(Umbral: {profit_threshold}%)")
                
                # Verificar si se debe vender
                if percentage_gain >= profit_threshold:
                    try:
                        logger.info(f"Ejecutando venta de {symbol} con {percentage_gain:.2f}% de ganancia "
                                    f"(umbral: {profit_threshold}%)")
                        
                        # Ejecutar la orden de venta
                        trade_result = self.executor.execute_trade(
                            side="SELL",
                            symbol=symbol_pair,
                            order_type="MARKET",
                            positions=current_balance,
                            reason=sell_reason,
                            percentage_gain=percentage_gain
                        )
                        
                        if trade_result:
                            logger.info(f"Venta de {symbol} ejecutada exitosamente")
                            
                            # Actualizar el activo en la base de datos si es necesario
                            with Session(self.engine) as session:
                                db_asset = session.merge(db_asset)
                                session.delete(db_asset)
                                session.commit()
                                logger.info(f"Activo {symbol} eliminado de la base de datos después de la venta")
                        else:
                            logger.error(f"Error al ejecutar la venta de {symbol}")
                            
                    except Exception as e:
                        logger.error(f"Error al ejecutar la venta de {symbol}: {e}")
                else:
                    logger.info(f"{symbol}: No se vende. Ganancia actual {percentage_gain:.2f}% por debajo del umbral de +{profit_threshold}%")
                    
                    # Registrar información de seguimiento
                    logger.info(f"Seguimiento {symbol}:")
                    logger.info(f"- Precio Actual: ${current_price:,.8f}")
                    logger.info(f"- Cantidad: {current_balance:,.8f}")
                    logger.info(f"- Precio de Compra: ${purchase_price:,.8f}")
                    logger.info(f"- Ganancia Actual: {percentage_gain:.2f}%")
                    logger.info(f"- Umbral de Venta: {profit_threshold:.2f}%")
                    
            except Exception as e:
                logger.error(f"Error al procesar el activo {symbol}: {e}")
            
            # Pequeña pausa entre activos para no sobrecargar la API
            time.sleep(1)
    
    def _make_action(self, action, symbol, average_buy_price, current_price, real_balance, percentage_gain, percentage_loss):
        if action == "vender pérdida":
            percentage_loss = ((average_buy_price - current_price) / average_buy_price) * 100
            logger.info(f"Stop loss alcanzado. Vender para limitar pérdidas. -{percentage_loss:,.2f}%.\n")

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
                    logger.info(f"Orden de venta por stop loss ejecutada para {symbol}.\n")
                else:
                    logger.error(f"Orden de venta por stop loss no se ha podido ejecutar para {symbol}.\n")
            except Exception as e:
                logger.error(f"Error al ejecutar la venta por stop loss para {symbol}: {e}")
        elif action == "vender ganancia":
            logger.info(f"Objetivo de ganancia alcanzado. Vender para asegurar ganancias. +{percentage_gain:,.2f}%.\n")

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
                    logger.info(f"Orden de venta por objetivo de ganancia ejecutada para {symbol}.\n")
                else:
                    logger.error(f"Orden de venta por objetivo de ganancia no se ha podido ejecutar para {symbol}.\n")
            except Exception as e:
                logger.error(f"Error al ejecutar la venta por objetivo de ganancia para {symbol}: {e}")
