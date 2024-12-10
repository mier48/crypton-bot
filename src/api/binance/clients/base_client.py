# src/api/binance/clients/base_client.py

import requests
import logging
from typing import Any, Dict, Optional
from requests.adapters import HTTPAdapter, Retry
from urllib.parse import urljoin
from config.binance import BINANCE_BASE_URL
from utils.logger import setup_logger

logger = setup_logger()

class BaseClient:
    def __init__(self, base_url: str = BINANCE_BASE_URL, timeout: int = 10):
        """
        Cliente base para manejar solicitudes HTTP a la API de Binance.
        """
        self.base_url = base_url
        self.session = requests.Session()
        retries = Retry(total=5, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.timeout = timeout

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Realiza una solicitud GET.
        """
        url = urljoin(self.base_url, endpoint)
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"GET request failed: {e}")
            logger.debug(f"Endpoint: {url}, Params: {params}, Headers: {headers}")
            return None

    def post(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Realiza una solicitud POST.
        """
        url = urljoin(self.base_url, endpoint)
        try:
            response = self.session.post(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            # Intenta obtener más detalles del error
            try:
                error_info = response.json()
                logger.error(f"HTTP error occurred: {http_err} - Detalles: {error_info}")
            except ValueError:
                # Si la respuesta no es JSON, simplemente registra el texto
                logger.error(f"HTTP error occurred: {http_err} - Respuesta: {response.text}")
            return None
        except requests.exceptions.RequestException as req_err:
            # Maneja otras excepciones de Requests
            logger.error(f"Request exception occurred: {req_err}")
            return None
