import time
import hmac
import hashlib
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from urllib.parse import urlencode
from datetime import datetime
from src.api.binance.clients.base_client import BaseClient, BinanceAPIError, RateLimitExceededError
from src.config.binance import (BINANCE_BASE_URL, BINANCE_API_KEY, BINANCE_SECRET_KEY)
from loguru import logger

# Para evitar importaciones circulares
if TYPE_CHECKING:
    from src.app.notifiers.telegram_notifier import TelegramNotifier

class BinanceAccountClient(BaseClient):
    def __init__(self):
        """
        Inicializa el cliente autenticado para interactuar con la API de Binance.
        """
        super().__init__(base_url=BINANCE_BASE_URL)
        
        self.api_key = BINANCE_API_KEY
        self.secret_key = BINANCE_SECRET_KEY.encode('utf-8')
        
        # Set API key in headers for authenticated requests
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key
        })
        
        self._telegram_notifier = None
    
    @property
    def telegram_notifier(self) -> 'TelegramNotifier':
        if self._telegram_notifier is None:
            from src.app.notifiers.telegram_notifier import TelegramNotifier
            self._telegram_notifier = TelegramNotifier()
        return self._telegram_notifier
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Genera una firma HMAC-SHA256 para los parámetros dados.
        """
        query_string = urlencode(params, doseq=True)
        signature = hmac.new(
            self.secret_key,
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_authenticated_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Agrega el timestamp y la firma a los parámetros.
        """
        if params is None:
            params = {}
            
        # Add timestamp and signature
        params["timestamp"] = int(time.time() * 1000)
        params["signature"] = self._generate_signature(params)
        
        return params
    
    def get_balance_summary(self) -> List[Dict[str, Any]]:
        """
        Obtiene el balance de la cuenta autenticada.
        
        Returns:
            List[Dict]: Lista de diccionarios con los balances de los activos.
                      Cada diccionario contiene:
                      - asset (str): Símbolo del activo (ej: 'BTC')
                      - free (float): Cantidad disponible para operar
                      - locked (float): Cantidad bloqueada en órdenes abiertas
                      - total (float): Suma de free + locked
                      - usd_value (float): Valor total en USDC (si se puede calcular)
        """
        try:
            logger.info("Obteniendo resumen de balance de Binance...")
            
            # Obtener parámetros autenticados
            params = self._get_authenticated_params()
            
            # Hacer la solicitud a la API
            response, headers = self._request('GET', 'api/v3/account', params=params)
            
            if not response or 'balances' not in response:
                logger.error("Respuesta de la API no contiene datos de balance")
                return []
            
            # Procesar los balances
            balances = []
            for balance in response['balances']:
                try:
                    asset = balance['asset']
                    free = float(balance['free'])
                    locked = float(balance['locked'])
                    total = free + locked
                    
                    # Solo incluir activos con saldo
                    if total > 0:
                        balances.append({
                            'asset': asset,
                            'free': free,
                            'locked': locked,
                            'total': total
                        })
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error al procesar balance para {balance.get('asset', 'unknown')}: {e}")
            
            logger.info(f"Se obtuvieron {len(balances)} activos con saldo")
            return balances
            
        except RateLimitExceededError as e:
            wait_seconds = (e.reset_time - datetime.now()).total_seconds()
            logger.warning(f"Límite de tasa alcanzado. Esperando {wait_seconds:.1f} segundos...")
            if wait_seconds > 0:
                time.sleep(min(wait_seconds, 60))  # No esperar más de 1 minuto
            # Reintentar una vez después de esperar
            return self.get_balance_summary()
            
        except BinanceAPIError as e:
            logger.error(f"Error en la API de Binance: {e.message} (Código: {e.error_code}, Status: {e.status_code})")
            return []
            
        except Exception as e:
            logger.exception(f"Error inesperado al obtener el balance: {str(e)}")
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

        Args:
            symbol: Par de trading (ej: 'BTCUSDT')
            side: 'BUY' o 'SELL'
            type_: Tipo de orden ('MARKET', 'LIMIT', etc.)
            quantity: Cantidad a operar (no usar con quote_order_qty para la misma orden)
            quote_order_qty: Cantidad en la moneda de cotización (solo para MARKET orders)
            price: Precio para órdenes LIMIT

        Returns:
            Dict con la respuesta de la orden o None si hay un error
        """
        logger.debug(f"Creando orden: symbol={symbol}, side={side}, type={type_}, quantity={quantity}, quote_order_qty={quote_order_qty}, price={price}")

        # Validar parámetros obligatorios
        if not symbol or not side or not type_:
            raise ValueError("Los parámetros 'symbol', 'side' y 'type_' son obligatorios.")

        # Convertir a mayúsculas para consistencia
        symbol = symbol.upper().strip()
        side = side.upper().strip()
        type_ = type_.upper().strip()

        # Verificar si el símbolo existe y está disponible para trading
        try:
            symbol_info = self.get_exchange_info(symbol=symbol)
            symbol_data = next((s for s in symbol_info.get('symbols', []) if s['symbol'] == symbol), None)
            
            if not symbol_data:
                error_msg = f"❌ Símbolo {symbol} no encontrado en el exchange"
                logger.error(error_msg)
                self.telegram_notifier.send_message(error_msg)
                return None
                
            # Verificar si el mercado está en estado TRADING
            market_status = symbol_data.get('status', 'UNKNOWN')
            if market_status != 'TRADING':
                error_msg = f"⚠️ Mercado {symbol} no disponible. Estado: {market_status}"
                logger.warning(error_msg)
                self.telegram_notifier.send_message(error_msg)
                return None
                
            # Verificar si el trading spot está habilitado
            spot_enabled = (
                symbol_data.get('isSpotTradingAllowed', False) or 
                'SPOT' in symbol_data.get('permissions', []) or
                any('SPOT' in perm_set for perm_set in symbol_data.get('permissionSets', []))
            )
            
            if not spot_enabled:
                error_msg = f"⚠️ Trading SPOT no habilitado para {symbol}"
                logger.warning(error_msg)
                self.telegram_notifier.send_message(error_msg)
                return None
                
            # Verificar si el símbolo está en mantenimiento
            if symbol_data.get('isLocked', False):
                error_msg = f"🔒 Símbolo {symbol} está en mantenimiento"
                logger.warning(error_msg)
                self.telegram_notifier.send_message(error_msg)
                return None
                
        except Exception as e:
            error_msg = f"❌ Error al verificar el estado del mercado {symbol}: {str(e)}"
            logger.error(error_msg)
            self.telegram_notifier.send_message(error_msg)
            return None
            
        params = {
            "symbol": symbol,
            "side": side,
            "type": type_,
            "newOrderRespType": "FULL",  # Para obtener toda la información de la orden
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000
        }

        try:
            if type_ == "MARKET":
                if quantity is not None:
                    params["quantity"] = f"{quantity:.8f}"
                elif quote_order_qty is not None:
                    params["quoteOrderQty"] = f"{quote_order_qty:.8f}"
                else:
                    raise ValueError("Para órdenes MARKET, debes especificar 'quantity' o 'quoteOrderQty'.")
            
            elif type_ == "LIMIT":
                if price is None or quantity is None:
                    raise ValueError("Las órdenes LIMIT requieren 'price' y 'quantity'.")
                params.update({
                    "price": f"{price:.8f}",
                    "quantity": f"{quantity:.8f}",
                    "timeInForce": "GTC"
                })
            else:
                raise ValueError(f"Tipo de orden no soportado: {type_}")

            # Agregar firma
            params["signature"] = self._generate_signature(params)

            endpoint = "api/v3/order"
            logger.debug(f"Enviando orden a {endpoint} con parámetros: {params}")
            
            response = self.post(endpoint, params=params)
            
            if isinstance(response, dict) and response.get('error'):
                # Manejar el error devuelto por el método post
                error_msg = (
                    f"❌ Error {response.get('status_code', '')} "
                    f"(Code: {response.get('code', 'N/A')}) - {side} {symbol}"
                )
                logger.error(error_msg)
                self.telegram_notifier.send_message(error_msg)
                return None
                
            if not response:
                error_msg = f"❌ Error: Respuesta vacía al crear orden {type_} {side} para {symbol}"
                logger.error(error_msg)
                self.telegram_notifier.send_message(error_msg)
                return None
                
            success_msg = f"✅ Orden {type_} {side} ejecutada para {symbol}. ID: {response.get('orderId')}"
            logger.info(success_msg)
            try:
                self.telegram_notifier.send_message(success_msg)
            except Exception as e:
                logger.error(f"Error al enviar notificación de éxito a Telegram: {e}")
            return response
            
        except Exception as e:
            error_msg = f"❌ Error al crear orden {type_} {side} para {symbol}: {str(e)}"
            logger.error(error_msg)
            try:
                self.telegram_notifier.send_message(error_msg)
            except Exception as e:
                logger.error(f"Error al enviar notificación de error a Telegram: {e}")
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

    def get_trade_fee_rate(self, symbol: str = "BTCUSDC") -> Optional[float]:
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

    def get_exchange_info(self, symbol: Optional[str] = None, symbols: Optional[List[str]] = None, 
                        permissions: Optional[Union[str, List[str]]] = None, 
                        symbol_status: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene información sobre el estado del exchange y los símbolos disponibles.
        
        Args:
            symbol: (Opcional) Símbolo específico para obtener información detallada.
            symbols: (Opcional) Lista de símbolos para obtener información detallada.
            permissions: (Opcional) Filtro por permisos (SPOT, MARGIN, LEVERAGED).
            symbol_status: (Opcional) Filtro por estado del símbolo (TRADING, HALT, BREAK).
            
        Returns:
            Dict con la información del exchange y los símbolos.
            
        Raises:
            ValueError: Si no se puede obtener la información del exchange.
        """
        endpoint = "api/v3/exchangeInfo"
        params = {}
        
        # Solo un tipo de parámetro de símbolo puede usarse a la vez
        if symbol and symbols:
            raise ValueError("No se pueden especificar 'symbol' y 'symbols' simultáneamente")
            
        if symbol:
            params["symbol"] = symbol.upper()
        elif symbols:
            if not isinstance(symbols, list):
                raise ValueError("'symbols' debe ser una lista de strings")
            params["symbols"] = json.dumps([s.upper() for s in symbols])
            
        # Añadir filtros opcionales
        if permissions:
            if isinstance(permissions, list):
                params["permissions"] = json.dumps(permissions)
            else:
                params["permissions"] = permissions
                
        if symbol_status:
            if symbol_status.upper() not in ["TRADING", "HALT", "BREAK"]:
                raise ValueError("symbol_status debe ser uno de: TRADING, HALT, BREAK")
            params["symbolStatus"] = symbol_status.upper()
            
        response = self.get(endpoint, params=params)
        
        if not response:
            raise ValueError("No se pudo obtener la información del exchange")
            
        return response

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
        order_id: Optional[int] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
        recv_window: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Obtiene todas las órdenes para un símbolo específico.
        
        Args:
            symbol: Par de trading (ej: 'BTCUSDC')
            order_id: ID de orden. Si se especifica, devuelve órdenes >= a este ID
            start_time: Timestamp en ms para filtrar órdenes desde (obligatorio si se usa end_time)
            end_time: Timestamp en ms para filtrar órdenes hasta (obligatorio si se usa start_time)
            limit: Número máximo de órdenes a devolver (1-1000, por defecto 500)
            recv_window: Ventana de recepción en ms (máx. 60000, por defecto 5000)
            
        Returns:
            List[Dict]: Lista de órdenes con sus detalles
            
        Raises:
            ValueError: Si los parámetros son inválidos
            BinanceAPIError: Si hay un error en la API de Binance
            
        Notes:
            - Si se especifica order_id, devuelve órdenes >= a ese ID
            - Si se especifican start_time y end_time, no se requiere order_id
            - El rango entre start_time y end_time no puede ser mayor a 24 horas
        """
        try:
            logger.info(f"Obteniendo órdenes para {symbol} (límite: {limit})")
            
            # Validar parámetros requeridos
            if not symbol:
                raise ValueError("El símbolo no puede estar vacío")
                
            if limit < 1 or limit > 1000:
                raise ValueError("El límite debe estar entre 1 y 1000")
                
            if recv_window < 1 or recv_window > 60000:
                raise ValueError("recv_window debe estar entre 1 y 60000")
            
            # Validar restricciones de tiempo
            if start_time is not None or end_time is not None:
                if start_time is None or end_time is None:
                    raise ValueError("Ambos start_time y end_time deben proporcionarse juntos")
                if not isinstance(start_time, int) or start_time < 0:
                    raise ValueError("start_time debe ser un timestamp en milisegundos")
                if not isinstance(end_time, int) or end_time < 0:
                    raise ValueError("end_time debe ser un timestamp en milisegundos")
                if end_time <= start_time:
                    raise ValueError("end_time debe ser mayor que start_time")
                if (end_time - start_time) > 24 * 60 * 60 * 1000:  # 24 horas en ms
                    raise ValueError("El rango de tiempo no puede ser mayor a 24 horas")
            
            # Construir parámetros de la solicitud
            params = {
                "symbol": symbol.upper(),
                "limit": limit,
            }
            
            # Añadir parámetros opcionales
            # if order_id is not None:
            #     if not isinstance(order_id, int) or order_id < 0:
            #         raise ValueError("order_id debe ser un entero positivo")
            #     params["orderId"] = order_id
                
            if start_time is not None:
                params["startTime"] = start_time
                params["endTime"] = end_time
            
            # Obtener parámetros autenticados
            params = self._get_authenticated_params(params)
            
            # Hacer la solicitud
            response, _ = self._request('GET', 'api/v3/allOrders', params=params)
            
            # Validar la respuesta
            if not isinstance(response, list):
                logger.error(f"Respuesta inesperada al obtener órdenes: {response}")
                return []
                
            logger.info(f"Se obtuvieron {len(response)} órdenes para {symbol}")
            return response
            
        except RateLimitExceededError as e:
            wait_seconds = (e.reset_time - datetime.now()).total_seconds()
            logger.warning(f"Límite de tasa alcanzado. Esperando {wait_seconds:.1f} segundos...")
            if wait_seconds > 0:
                time.sleep(min(wait_seconds, 60))  # No esperar más de 1 minuto
            # Reintentar una vez después de esperar
            return self.get_all_orders(
                symbol=symbol,
                order_id=order_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                recv_window=recv_window
            )
            
        except BinanceAPIError as e:
            logger.error(f"Error en la API de Binance al obtener órdenes: {e.message} (Código: {e.error_code})")
            raise  # Relanzar para manejo superior
            
        except ValueError as e:
            logger.error(f"Error de validación: {str(e)}")
            raise  # Relanzar para manejo superior
            
        except Exception as e:
            logger.exception(f"Error inesperado al obtener órdenes: {str(e)}")
            raise  # Relanzar para manejo superior
