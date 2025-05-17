import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from src.api.binance.clients.account_client import BinanceAccountClient
from src.api.binance.clients.market_client import BinanceMarketClient
from src.utils.date_utils import interval_to_milliseconds
from src.utils.logger import setup_logger

logger = setup_logger()

class BinanceDataManager:
    def __init__(self):
        """
        Inicializa el administrador de datos, unificando acceso a clientes de Binance.
        """
        self.market_client = BinanceMarketClient()
        self.account_client = BinanceAccountClient()

    ## Operaciones de Precios y Datos de Mercado
    def get_price(self, symbol: str) -> Optional[float]:
        """
        Obtiene el precio actual de un par de mercado.
        """
        return self.market_client.get_price(symbol)

    def fetch_historical_data(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        interval: str = "1d",
        limit: int = 500
    ) -> Optional[List[Any]]:
        """
        Obtiene datos históricos para un símbolo y período específicos.
        """
        # Utiliza limit para paginar hasta 1000 según necesidad
        return self.market_client.fetch_historical_data(symbol, start_time, end_time, interval, limit)

    def get_top_gainers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con mayor incremento de precio en las últimas 24h.
        """
        return self.market_client.get_top_gainers(limit)

    def get_top_losers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con mayor decremento de precio en las últimas 24h.
        """
        return self.market_client.get_top_losers(limit)

    def get_most_popular(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas más populares en Binance por volumen.
        """
        return self.market_client.get_most_popular(limit)

    def get_popular_mid_price(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con precios intermedios más populares.
        """
        return self.market_client.get_popular_mid_price(limit)

    def get_popular_low_price(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con precios bajos más populares.
        """
        return self.market_client.get_popular_low_price(limit)

    def get_popular_extra_low_price(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con precios muy bajos más populares.
        """
        return self.market_client.get_popular_extra_low_price(limit)

    def check_market_pair(self, pair: str) -> bool:
        """
        Verifica si un par de mercado está disponible en Binance.
        """
        return self.market_client.check_market_pair(pair)

    def get_top_cryptocurrencies(self, top_n: int = 10, by: str = "price") -> List[Dict[str, Any]]:
        """
        Obtiene las principales criptomonedas ordenadas por precio o volumen.
        """
        return self.market_client.get_top_cryptocurrencies(top_n, by)
    
    def get_popular_by_price_range(self, min_price: float, max_price: float, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas más populares entre un rango de precios.
        """
        return self.market_client.get_popular_by_price_range(min_price, max_price, limit)

    def get_exchange_info(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Obtiene metadatos de exchangeInfo (pares listados) con cache.
        """
        return self.market_client.get_exchange_info(force)

    def get_all_symbols(self) -> List[str]:
        """
        Devuelve lista de todos los símbolos disponibles en Binance.
        """
        return self.market_client.get_all_symbols()

    ## Operaciones de Cuenta y Trading
    def get_balance_summary(self) -> List[Dict[str, Any]]:
        """
        Obtiene el resumen de balances de la cuenta autenticada.
        """
        return self.account_client.get_balance_summary()

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
        return self.account_client.create_order(symbol, side, type_, quantity, quote_order_qty, price)

    def get_all_orders(
        self,
        symbol: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene todas las órdenes realizadas para un símbolo específico.
        """
        return self.account_client.get_all_orders(symbol, limit, start_time, end_time)

    ## Funcionalidades Combinadas
    def fetch_combined_data(self, symbol: str = "BTCUSDC") -> Dict[str, Any]:
        """
        Combina datos de precio y balance.
        """
        price = self.get_price(symbol)
        balances = self.get_balance_summary()
        balance_for_symbol = next(
            (b for b in balances if b['asset'] == symbol[:-4]), None
        )
        combined_data = {"price": price, "balance": balance_for_symbol}
        logger.debug(f"Datos combinados: {combined_data}")
        return combined_data

    def fetch_market_and_account_data(self, symbol: str = "BTCUSDC", top_n: int = 10) -> Dict[str, Any]:
        """
        Obtiene precio, balances y las principales criptomonedas del mercado.
        """
        price = self.get_price(symbol)
        balances = self.get_balance_summary()
        top_cryptos = self.get_top_cryptocurrencies(top_n)
        combined_data = {"price": price, "balances": balances, "top_cryptos": top_cryptos}
        logger.debug(f"Datos de mercado y cuenta: {combined_data}")
        return combined_data

    def fetch_symbol_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene los datos de un símbolo específico.
        """
        return self.market_client.get("api/v3/exchangeInfo", params={"symbol": symbol})
    
    def get_market_volatility(
        self,
        symbol: str = "BTCUSDC",
        interval: str = "1h",
        lookback: int = 24
    ) -> Optional[float]:
        """
        Calcula la volatilidad del mercado para un símbolo específico basado en los datos de velas.

        :param symbol: Par de trading, por ejemplo, 'BTCUSDC'.
        :param interval: Intervalo de tiempo de las velas, por ejemplo, '1h' para una hora.
        :param lookback: Número de velas a considerar para el cálculo.
        :return: Volatilidad calculada como la desviación estándar de los rendimientos logarítmicos.
        """
        try:
            # Calcular el tiempo actual y el tiempo de inicio
            end_time_dt = datetime.now(timezone.utc)
            interval_ms = interval_to_milliseconds(interval)
            start_time_dt = end_time_dt - timedelta(milliseconds=interval_ms * lookback)

            # Convertir datetime a timestamp en milisegundos
            end_time = int(end_time_dt.timestamp() * 1000)
            start_time = int(start_time_dt.timestamp() * 1000)

            # Obtener datos de velas de Binance
            klines = self.fetch_historical_data(symbol=symbol, interval=interval, start_time=start_time, end_time=end_time)
            if not klines:
                logger.error("No se pudieron obtener datos de velas de Binance.")
                return None

            # Crear un DataFrame con los precios de cierre
            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['close'] = df['close'].astype(float)

            # Calcular los rendimientos logarítmicos
            df['log_return'] = np.log(df['close'] / df['close'].shift(1))
            df = df.dropna()

            # Calcular la desviación estándar de los rendimientos
            volatility = df['log_return'].std()

            logger.debug(f"Volatilidad calculada para {symbol}: {volatility:.6f}")

            return volatility

        except Exception as e:
            logger.error(f"Error al calcular la volatilidad del mercado: {e}")
            return None
