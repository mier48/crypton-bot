import requests
import time
from typing import Any, Dict, Optional, Union, Tuple
from requests.exceptions import RequestException, HTTPError, Timeout, ConnectionError as RequestsConnectionError
from datetime import datetime, timedelta
from dataclasses import dataclass
from urllib.parse import urljoin
from src.config.binance import BINANCE_BASE_URL
from loguru import logger

@dataclass
class RateLimit:
    limit: int
    remaining: int
    reset_time: datetime

class RateLimitExceededError(Exception):
    """Exception raised when rate limit is exceeded."""
    def __init__(self, message: str, reset_time: datetime):
        self.message = message
        self.reset_time = reset_time
        super().__init__(self.message)

class BinanceAPIError(Exception):
    """Exception raised for Binance API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, error_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)

class BaseClient:
    def __init__(self, base_url: str = BINANCE_BASE_URL, timeout: int = 10):
        """
        Cliente base para manejar solicitudes HTTP a la API de Binance.
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        # Default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'X-MBX-APIKEY': ''  # Will be set by the account client
        })
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests by default
        self.rate_limits = {}  # Will store rate limit info by endpoint
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        
        # Set up retries for the session
        retries = 5
        self.session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))
        self.timeout = timeout

    def _update_rate_limits(self, response: requests.Response) -> None:
        """Update rate limit information from response headers."""
        headers = response.headers
        
        # Binance uses different rate limit headers for different endpoints
        for weight_type in ['x-mbx-used-weight-1m', 'x-mbx-order-count-1m']:
            if weight_type in headers:
                used_weight = int(headers[weight_type])
                # Binance doesn't always send the limit in the headers
                limit = int(headers.get(f'{weight_type}-limit', '1200'))
                reset_time = datetime.now() + timedelta(minutes=1)  # Reset in 1 minute
                
                self.rate_limits[weight_type] = RateLimit(
                    limit=limit,
                    remaining=limit - used_weight,
                    reset_time=reset_time
                )
        
        # Handle IP based rate limits
        if 'x-sapi-used-ip-weight-1m' in headers:
            used_weight = int(headers['x-sapi-used-ip-weight-1m'])
            limit = int(headers.get('x-sapi-limit-ip-weight-1m', '12000'))
            reset_time = datetime.now() + timedelta(minutes=1)
            
            self.rate_limits['ip'] = RateLimit(
                limit=limit,
                remaining=limit - used_weight,
                reset_time=reset_time
            )
    
    def _check_rate_limits(self) -> None:
        """Check if we're about to hit rate limits."""
        now = datetime.now()
        
        for limit_name, limit in self.rate_limits.items():
            if limit.remaining <= 10:  # Leave some buffer
                wait_time = (limit.reset_time - now).total_seconds()
                if wait_time > 0:
                    raise RateLimitExceededError(
                        f"Approaching rate limit for {limit_name}. "
                        f"{limit.remaining} requests remaining. "
                        f"Resets in {wait_time:.1f} seconds.",
                        reset_time=limit.reset_time
                    )
    
    def _handle_api_error(self, response: requests.Response) -> None:
        """Handle API errors and raise appropriate exceptions."""
        try:
            error_data = response.json()
        except ValueError:
            error_data = {}
        
        status_code = response.status_code
        error_msg = error_data.get('msg', response.text or 'Unknown error')
        error_code = error_data.get('code')
        
        if status_code == 429:  # Too Many Requests
            retry_after = int(response.headers.get('Retry-After', '1'))
            reset_time = datetime.now() + timedelta(seconds=retry_after)
            raise RateLimitExceededError(
                f"Rate limit exceeded: {error_msg}",
                reset_time=reset_time
            )
        
        raise BinanceAPIError(
            f"API Error {status_code}: {error_msg}",
            status_code=status_code,
            error_code=error_code
        )
    
    def _wait_for_rate_limit(self) -> None:
        """Wait until we can make the next request based on rate limits."""
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Tuple[Union[dict, list], dict]:
        """
        Make an HTTP request with rate limiting and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments to pass to requests.request()
            
        Returns:
            Tuple of (parsed JSON response, headers)
            
        Raises:
            RateLimitExceededError: If rate limit would be exceeded
            BinanceAPIError: For API errors
            RequestException: For network errors
        """
        url = urljoin(self.base_url, endpoint)
        
        for attempt in range(self.max_retries + 1):
            try:
                self._wait_for_rate_limit()
                self._check_rate_limits()
                
                logger.debug(f"Making {method} request to {url}")
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                
                # Update rate limit information
                self._update_rate_limits(response)
                
                # Return parsed JSON and headers
                return response.json(), dict(response.headers)
                
            except HTTPError as e:
                if e.response is not None:
                    if e.response.status_code == 429:  # Rate limited
                        retry_after = int(e.response.headers.get('Retry-After', '1'))
                        if attempt < self.max_retries:
                            time.sleep(retry_after)
                            continue
                    self._handle_api_error(e.response)
                raise
                
            except (RequestsConnectionError, Timeout) as e:
                if attempt == self.max_retries:
                    logger.error(f"Failed to connect to {url} after {self.max_retries} attempts")
                    raise
                time.sleep(self.retry_delay * (attempt + 1))
                
            except Exception as e:
                logger.error(f"Unexpected error during request to {url}: {str(e)}")
                if attempt == self.max_retries:
                    raise
                time.sleep(self.retry_delay * (attempt + 1))
        
        # This should never be reached due to the raises above, but just in case
        raise RequestException(f"Failed to complete request to {url} after {self.max_retries} attempts")

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Realiza una solicitud GET.
        """
        url = urljoin(self.base_url, endpoint)
        try:
            #logger.debug(f"GET request to {url} with params {params} and headers {headers}")
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
            logger.debug(f"POST request to {url} with params {params} and headers {headers}")
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
