# src/api/binance/clients/account_client.py

import time
import hmac
import hashlib
from typing import Any, Dict, Optional, List
from urllib.parse import urlencode
from api.binance.clients.base_client import BaseClient
from config.binance import (BINANCE_BASE_URL, BINANCE_API_KEY, BINANCE_SECRET_KEY)
from utils.logger import setup_logger

logger = setup_logger()

class BinanceAccountClient(BaseClient):
    def __init__(self):
        """
        Inicializa el cliente autenticado para interactuar con la API de Binance.
        """
        super().__init__(base_url=BINANCE_BASE_URL)

        self.api_key = BINANCE_API_KEY
        self.secret_key = BINANCE_SECRET_KEY.encode('utf-8')

        self.headers = {
            "X-MBX-APIKEY": self.api_key
        }

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Genera una firma HMAC-SHA256 para los parámetros dados.
        """
        query_string = urlencode(params)
        signature = hmac.new(self.secret_key, query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        return signature

    def _get_authenticated_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Agrega el timestamp y la firma a los parámetros.
        """
        if params is None:
            params = {}
        params["timestamp"] = int(time.time() * 1000)
        params["signature"] = self._generate_signature(params)
        return params

    def get_balance_summary(self) -> List[Dict[str, Any]]:
        """
        Obtiene el balance de la cuenta autenticada.
        """
        endpoint = "api/v3/account"
        params = self._get_authenticated_params()

        response = self.get(endpoint, params=params, headers=self.headers)
        if response and "balances" in response:
            balances = [
                {"asset": balance["asset"], "free": float(balance["free"]), "locked": float(balance["locked"])}
                for balance in response["balances"]
                if float(balance["free"]) > 0 or float(balance["locked"]) > 0
            ]
            # logger.info(f"Balances obtenidos: {balances}")
            return balances
        else:
            logger.error("No se pudieron obtener los balances.")
            return []

    def create_order(
        self,
        symbol: str,
        side: str,
        type_: str,
        quantity: Optional[float] = None,
        quote_order_qty: Optional[float] = None,
        price: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Crea una orden en Binance.
        """
        logger.debug(f"Creando orden: symbol={symbol}, side={side}, type={type_}, quantity={quantity}, quote_order_qty={quote_order_qty}, price={price}")

        # Validar parámetros obligatorios
        if not symbol or not side or not type_:
            raise ValueError("Los parámetros 'symbol', 'side' y 'type_' son obligatorios.")

        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": type_.upper(),
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000  # Opcional pero recomendado
        }

        if type_ == "MARKET":
            if quantity:
                params["quantity"] = quantity
            elif quote_order_qty:
                params["quoteOrderQty"] = f"{quote_order_qty:.8f}"
            else:
                raise ValueError("Para órdenes MARKET, debes especificar 'quantity' o 'quoteOrderQty'.")
        elif type_ == "LIMIT":
            if not price or not quantity:
                raise ValueError("Las órdenes LIMIT requieren 'price' y 'quantity'.")
            params["price"] = f"{price:.8f}"
            params["quantity"] = f"{quantity:.8f}"
            params["timeInForce"] = "GTC"
        else:
            raise ValueError(f"Tipo de orden desconocido: {type_}")

        # Agregar firma
        params["signature"] = self._generate_signature(params)

        endpoint = "api/v3/order"
        response = self.post(endpoint, params=params, headers=self.headers)

        if response:
            # logger.info(f"Orden creada exitosamente: {response}")
            return response
        else:
            logger.error("Error al crear la orden.")
            return None

    def get_trade_fees(self, symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Obtiene las tarifas de trading.
        """
        endpoint = "sapi/v1/asset/tradeFee"
        params = self._get_authenticated_params()

        if symbol:
            params["symbol"] = symbol

        response = self.get(endpoint, params=params)
        if response:
            logger.info(f"Tarifas de trading obtenidas: {response}")
            return response
        else:
            logger.error("Error al obtener tarifas de trading.")
            return None

    def get_trade_fee_rate(self, symbol: str = "BTCUSDT") -> Optional[float]:
        """
        Obtiene la tarifa total promedio (maker y taker) para un par específico.
        """
        response = self.get_trade_fees(symbol=symbol)
        if response and isinstance(response, dict) and "makerCommission" in response and "takerCommission" in response:
            maker_fee = float(response["makerCommission"])
            taker_fee = float(response["takerCommission"])
            average_fee = (maker_fee + taker_fee) / 2
            logger.debug(f"Tarifa promedio para {symbol}: {average_fee}")
            return average_fee
        else:
            logger.error(f"No se pudo obtener la tarifa para el par {symbol}.")
            return None

    def get_symbol_filters(self, symbol: str) -> Dict[str, Any]:
        """
        Obtiene los filtros del mercado para un símbolo específico.
        """
        endpoint = "api/v3/exchangeInfo"
        params = {"symbol": symbol}
        response = self.get(endpoint, params=params)

        if not response or "symbols" not in response:
            raise ValueError(f"No se pudo obtener información del mercado para {symbol}.")

        symbol_info = next((s for s in response["symbols"] if s["symbol"] == symbol), None)
        if not symbol_info:
            raise ValueError(f"El símbolo {symbol} no está disponible.")

        filters = {f["filterType"]: f for f in symbol_info["filters"]}

        if "LOT_SIZE" not in filters or "MIN_NOTIONAL" not in filters:
            raise ValueError(f"Los filtros necesarios no están disponibles para {symbol}.")

        return {
            "lot_size": filters["LOT_SIZE"],
            "min_notional": filters["MIN_NOTIONAL"]
        }

    def validate_order(self, symbol: str, quantity: float) -> None:
        """
        Valida que la cantidad cumple con los filtros de mercado para el símbolo.
        """
        filters = self.get_symbol_filters(symbol)

        lot_size = filters.get("lot_size", {})
        min_qty = float(lot_size.get("minQty", 0))
        max_qty = float(lot_size.get("maxQty", float('inf')))
        step_size = float(lot_size.get("stepSize", 1))

        if quantity < min_qty:
            raise ValueError(f"La cantidad {quantity} es menor que el mínimo permitido ({min_qty}).")
        if quantity > max_qty:
            raise ValueError(f"La cantidad {quantity} es mayor que el máximo permitido ({max_qty}).")
        if (quantity * (10 ** 8)) % (step_size * (10 ** 8)) != 0:
            raise ValueError(f"La cantidad {quantity} no cumple con el incremento permitido ({step_size}).")

    def get_all_orders(
        self,
        symbol: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene todas las órdenes para un símbolo específico.
        """
        endpoint = "api/v3/allOrders"
        params = {
            "symbol": symbol,
            "limit": limit
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        # Agregar firma
        params = self._get_authenticated_params(params)

        response = self.get(endpoint, params=params, headers=self.headers)
        if response:
            # logger.info(f"Órdenes obtenidas: {response}")
            return response
        else:
            logger.error("Error al obtener órdenes.")
            return None
