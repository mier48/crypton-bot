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
        # Cache para estadísticas de 24h y exchange info
        self._ticker_24hr_cache: Optional[List[Dict[str, Any]]] = None
        self._exchange_info_cache: Optional[List[Dict[str, Any]]] = None

    def _get_24hr_data(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Obtiene y cachea globalmente los datos de ticker 24h.
        """
        if force or self._ticker_24hr_cache is None:
            data = self.get("api/v3/ticker/24hr") or []
            self._ticker_24hr_cache = data
        return self._ticker_24hr_cache

    def _filter_usdc(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [coin for coin in data if coin.get("symbol", "").endswith("USDC")]

    def get_exchange_info(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Obtiene y cachea la información completa de exchangeInfo (pares disponibles).
        """
        if force or self._exchange_info_cache is None:
            info = self.get("api/v3/exchangeInfo") or {}
            self._exchange_info_cache = info.get("symbols", [])
        return self._exchange_info_cache

    def get_all_symbols(self) -> List[str]:
        """
        Devuelve la lista de todos los símbolos disponibles.
        """
        symbols = self.get_exchange_info() or []
        return [s.get("symbol") for s in symbols if s.get("symbol")]

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
            logger.debug(f"No se pudo obtener el precio para {symbol}.")
            return None

    def get_top_cryptocurrencies(self, top_n: int = 10, by: str = "price") -> List[Dict[str, Any]]:
        """
        Obtiene las principales criptomonedas por precio o volumen.
        """
        market_data = self._get_24hr_data()
        usdc_pairs = self._filter_usdc(market_data)
        if by not in ("price", "volume"):
            logger.warning(f"Criterio desconocido: {by}. Usando 'price'.")
            by = "price"
        key = "lastPrice" if by == "price" else "quoteVolume"
        sorted_pairs = sorted(usdc_pairs, key=lambda x: float(x.get(key, 0)), reverse=True)
        top_cryptos = sorted_pairs[:top_n]
        # logger.info(f"Top {top_n} criptomonedas por {by}: {top_cryptos}")
        return top_cryptos

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
        endpoint = "api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        data = self.get(endpoint, params=params)
        if data:
            # logger.info(f"Datos históricos obtenidos para {symbol}.")
            return data
        else:
            logger.debug(f"debug al obtener datos históricos. Endpoint: {endpoint} | Params: {params} | Response: {data}")
            return None

    def get_top_gainers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con mayor incremento de precio en las últimas 24h.
        """
        data = self._get_24hr_data()
        pairs = self._filter_usdc(data)
        top_gainers = sorted(pairs, key=lambda x: float(x.get('priceChangePercent', 0)), reverse=True)[:limit]
        # logger.info(f"Top {limit} ganadores: {top_gainers}")
        return top_gainers

    def get_top_losers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con mayor decremento de precio en las últimas 24h.
        """
        data = self._get_24hr_data()
        pairs = self._filter_usdc(data)
        top_losers = sorted(pairs, key=lambda x: float(x.get('priceChangePercent', 0)))[:limit]
        # logger.info(f"Top {limit} perdedores: {top_losers}")
        return top_losers

    def get_most_popular(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas más populares en Binance por volumen.
        """
        data = self._get_24hr_data()
        pairs = self._filter_usdc(data)
        most_popular = sorted(pairs, key=lambda x: float(x.get('volume', 0)), reverse=True)[:limit]
        # logger.info(f"Criptomonedas más populares: {most_popular}")
        return most_popular

    def get_popular_mid_price(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con precios intermedios más populares.
        """
        data = self._get_24hr_data()
        pairs = self._filter_usdc(data)
        popular_mid_price = [c for c in pairs if 0.5 <= float(c.get('lastPrice', 0)) <= 2.5]
        popular_mid_price_sorted = sorted(popular_mid_price, key=lambda x: float(x.get('volume', 0)), reverse=True)[:limit]
        # logger.info(f"Criptomonedas populares con precio intermedio: {popular_mid_price_sorted}")
        return popular_mid_price_sorted

    def get_popular_low_price(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con precios bajos más populares.
        """
        data = self._get_24hr_data()
        pairs = self._filter_usdc(data)
        popular_low_price = [c for c in pairs if 0.01 <= float(c.get('lastPrice', 0)) <= 0.5]
        popular_low_price_sorted = sorted(popular_low_price, key=lambda x: float(x.get('volume', 0)), reverse=True)[:limit]
        # logger.info(f"Criptomonedas populares con precio bajo: {popular_low_price_sorted}")
        return popular_low_price_sorted

    def get_popular_extra_low_price(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas con precios muy bajos más populares.
        """
        data = self._get_24hr_data()
        pairs = self._filter_usdc(data)
        popular_extra_low_price = [c for c in pairs if 0.00001 <= float(c.get('lastPrice', 0)) <= 0.01]
        popular_extra_low_price_sorted = sorted(popular_extra_low_price, key=lambda x: float(x.get('volume', 0)), reverse=True)[:limit]
        # logger.info(f"Criptomonedas populares con precio muy bajo: {popular_extra_low_price_sorted}")
        return popular_extra_low_price_sorted

    def get_popular_by_price_range(self, min_price: float, max_price: float, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Obtiene las criptomonedas populares dentro de un rango de precios.
        
        :param min_price: Precio mínimo para filtrar.
        :param max_price: Precio máximo para filtrar.
        :param limit: Número máximo de resultados a devolver.
        :return: Lista de criptomonedas populares dentro del rango de precios.
        """
        data = self._get_24hr_data()
        pairs = self._filter_usdc(data)
        filtered_pairs = [c for c in pairs if min_price <= float(c.get('lastPrice', 0)) <= max_price]
        sorted_pairs = sorted(filtered_pairs, key=lambda x: float(x.get('volume', 0)), reverse=True)[:limit]
        logger.debug(f"Criptomonedas populares en rango {min_price}-{max_price}: {sorted_pairs}")
        return sorted_pairs
