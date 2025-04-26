import requests
from requests import Session
from requests.exceptions import RequestException, HTTPError
from config.coingecko import API_URL, LANGUAGE
from utils.logger import setup_logger
from typing import Optional, Dict, Any, List

logger = setup_logger()

class CoinGeckoClient:
    def __init__(self):
        self.base_url = API_URL
        self.session = Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.timeout = 10  # Tiempo de espera en segundos
        self.coins = self._fetch_coins()

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Realiza una solicitud GET a la API de CoinGecko.
        """
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except HTTPError as http_err:
            logger.error(f"HTTP error: {http_err}")
        except RequestException as req_err:
            logger.error(f"Request error: {req_err}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        return None

    def _fetch_coins(self) -> List[Dict[str, Any]]:
        """
        Obtiene la lista completa de monedas de CoinGecko.
        """
        data = self._make_request("coins/list")
        if data:
            return data
        logger.error("No se pudo obtener la lista de monedas.")
        return []

    def _get_coin_id(self, symbol: str) -> Optional[str]:
        """
        Busca el ID de una moneda a partir de su símbolo.
        """
        keywords_to_remove = ["usd", "usdc", "usdc", "eur"]
        symbol_cleaned = symbol.lower()
        for keyword in keywords_to_remove:
            symbol_cleaned = symbol_cleaned.replace(keyword, "")
        
        coin_id = next((coin['id'] for coin in self.coins if coin['symbol'].lower() == symbol_cleaned), None)
        if not coin_id:
            logger.error(f"No se encontró un identificador en CoinGecko para '{symbol}'.")
        return coin_id

    def fetch_crypto_news(self, symbol: str) -> Optional[str]:
        """
        Obtiene información relevante sobre una criptomoneda.
        """
        coin_id = self._get_coin_id(symbol)
        if not coin_id:
            return None

        data = self._make_request(f"coins/{coin_id}")
        if data:
            return data.get("description", {}).get(LANGUAGE, "No hay descripción disponible.")
        logger.error(f"No se encontró información para la moneda '{symbol}'.")
        return None

    def get_global_data(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene datos globales del mercado de criptomonedas.
        """
        data = self._make_request("global")
        if data and "data" in data:
            return data["data"]
        logger.error("No se pudieron obtener los datos globales.")
        return None

    def get_markets_data(
        self, 
        vs_currency: str = "usd", 
        order: str = "market_cap_desc", 
        per_page: int = 100, 
        page: int = 1, 
        sparkline: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene datos de mercado para múltiples criptomonedas.
        """
        params = {
            "vs_currency": vs_currency,
            "order": order,
            "per_page": per_page,
            "page": page,
            "sparkline": str(sparkline).lower()
        }
        return self._make_request("coins/markets", params)

    def get_market_chart(self, coin_id: str, vs_currency: str = "usd", days: int = 1) -> Optional[Dict[str, Any]]:
        """
        Obtiene datos históricos de mercado para una criptomoneda específica.
        """
        params = {
            "vs_currency": vs_currency,
            "days": days
        }
        return self._make_request(f"coins/{coin_id}/market_chart", params)
