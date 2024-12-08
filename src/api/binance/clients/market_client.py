# src/api/binance/clients/market_client.py

from typing import Any, Dict, List, Optional
from api.binance.clients.base_client import BaseClient
from utils.logger import setup_logger
from config.binance import BINANCE_BASE_URL

logger = setup_logger()

class BinanceMarketClient(BaseClient):
    def __init__(self, base_url: str = None):
        """
        Cliente para interactuar con los endpoints públicos del mercado de Binance.
        """
        super().__init__(base_url=base_url or BINANCE_BASE_URL)

    def check_market_pair(self, pair: str) -> bool:
        """
        Verifica si un par de mercado está disponible en Binance.
        """
        endpoint = "api/v3/exchangeInfo"
        params = {"symbol": pair}
        response = self.get(endpoint, params=params)
        if response and "symbols" in response:
            is_available = any(symbol["symbol"] == pair for symbol in response["symbols"])
            logger.debug(f"Verificación del par {pair}: {'Disponible' if is_available else 'No disponible'}")
            return is_available
        return False

    def get_price(self, symbol: str) -> Optional[float]:
        """
        Obtiene el precio actual de un par de mercado.
        """
        endpoint = "api/v3/ticker/price"
        params = {"symbol": symbol}
        data = self.get(endpoint, params=params)
        if data and "price" in data:
            price = float(data["price"])
            logger.debug(f"Precio de {symbol}: {price}")
            return price
        else:
            logger.error(f"No se pudo obtener el precio para {symbol}.")
            return None

    def get_top_cryptocurrencies(self, top_n: int = 10, by: str = "price") -> List[Dict[str, Any]]:
        """
        Obtiene las principales criptomonedas por precio o volumen.
        """
        endpoint = "api/v3/ticker/24hr"
        market_data = self.get(endpoint)

        if not market_data:
            logger.error("No se pudo obtener información del mercado.")
            return []

        usdt_pairs = [pair for pair in market_data if pair["symbol"].endswith("USDT")]

        if by == "price":
            sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x["lastPrice"]), reverse=True)
        elif by == "volume":
            sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x["quoteVolume"]), reverse=True)
        else:
            logger.warning(f"Criterio desconocido: {by}. Usando 'price' por defecto.")
            sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x["lastPrice"]), reverse=True)

        top_cryptos = sorted_pairs[:top_n]
        # logger.info(f"Top {top_n} criptomonedas por {by}: {top_cryptos}")
        return top_cryptos

    def fetch_historical_data(
        self,
        symbol: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        interval: str = "1d"
    ) -> Optional[List[Any]]:
        """
        Obtiene datos históricos para un símbolo y período específicos.
        """
        endpoint = "api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval
        }

        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time

        data = self.get(endpoint, params=params)
        if data:
            # logger.info(f"Datos históricos obtenidos para {symbol}.")
            return data
        else:
            logger.error("Error al obtener datos históricos.")
            return None

    def get_top_gainers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con mayor incremento de precio en las últimas 24h.
        """
        endpoint = "api/v3/ticker/24hr"
        data = self.get(endpoint)

        if not data:
            logger.error("No se pudo obtener información del mercado.")
            return []

        usdt_pairs = [coin for coin in data if coin['symbol'].endswith('USDT')]
        top_gainers = sorted(usdt_pairs, key=lambda x: float(x['priceChangePercent']), reverse=True)[:limit]
        # logger.info(f"Top {limit} ganadores: {top_gainers}")
        return top_gainers

    def get_top_losers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con mayor decremento de precio en las últimas 24h.
        """
        endpoint = "api/v3/ticker/24hr"
        data = self.get(endpoint)

        if not data:
            logger.error("No se pudo obtener información del mercado.")
            return []

        usdt_pairs = [coin for coin in data if coin['symbol'].endswith('USDT')]
        top_losers = sorted(usdt_pairs, key=lambda x: float(x['priceChangePercent']))[:limit]
        # logger.info(f"Top {limit} perdedores: {top_losers}")
        return top_losers

    def get_most_popular(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas más populares en Binance por volumen.
        """
        endpoint = "api/v3/ticker/24hr"
        data = self.get(endpoint)

        if not data:
            logger.error("No se pudo obtener información del mercado.")
            return []

        usdt_pairs = [coin for coin in data if coin['symbol'].endswith('USDT')]
        most_popular = sorted(usdt_pairs, key=lambda x: float(x['volume']), reverse=True)[:limit]
        # logger.info(f"Criptomonedas más populares: {most_popular}")
        return most_popular

    def get_popular_mid_price(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con precios intermedios más populares.
        """
        endpoint = "api/v3/ticker/24hr"
        data = self.get(endpoint)

        if not data:
            logger.error("No se pudo obtener información del mercado.")
            return []

        usdt_pairs = [coin for coin in data if coin['symbol'].endswith('USDT')]
        popular_mid_price = [coin for coin in usdt_pairs if 0.5 <= float(coin['lastPrice']) <= 2.5]
        popular_mid_price_sorted = sorted(popular_mid_price, key=lambda x: float(x['volume']), reverse=True)[:limit]
        # logger.info(f"Criptomonedas populares con precio intermedio: {popular_mid_price_sorted}")
        return popular_mid_price_sorted

    def get_popular_low_price(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con precios bajos más populares.
        """
        endpoint = "api/v3/ticker/24hr"
        data = self.get(endpoint)

        if not data:
            logger.error("No se pudo obtener información del mercado.")
            return []

        usdt_pairs = [coin for coin in data if coin['symbol'].endswith('USDT')]
        popular_low_price = [coin for coin in usdt_pairs if 0.01 <= float(coin['lastPrice']) <= 0.5]
        popular_low_price_sorted = sorted(popular_low_price, key=lambda x: float(x['volume']), reverse=True)[:limit]
        # logger.info(f"Criptomonedas populares con precio bajo: {popular_low_price_sorted}")
        return popular_low_price_sorted

    def get_popular_extra_low_price(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con precios muy bajos más populares.
        """
        endpoint = "api/v3/ticker/24hr"
        data = self.get(endpoint)

        if not data:
            logger.error("No se pudo obtener información del mercado.")
            return []

        usdt_pairs = [coin for coin in data if coin['symbol'].endswith('USDT')]
        popular_extra_low_price = [coin for coin in usdt_pairs if 0.00001 <= float(coin['lastPrice']) <= 0.01]
        popular_extra_low_price_sorted = sorted(popular_extra_low_price, key=lambda x: float(x['volume']), reverse=True)[:limit]
        # logger.info(f"Criptomonedas populares con precio muy bajo: {popular_extra_low_price_sorted}")
        return popular_extra_low_price_sorted
