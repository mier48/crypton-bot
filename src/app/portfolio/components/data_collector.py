from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
from datetime import datetime
import numpy as np
from src.api.binance.data_manager import BinanceDataManager
from src.app.portfolio.models.portfolio_state import PortfolioState
from loguru import logger

class DataCollector:
    """
    Componente responsable de recolectar datos de mercado y balances para el análisis de portafolio.
    """
    
    def __init__(self, data_manager: BinanceDataManager, market_data_days: int = 30):
        """
        Inicializa el recolector de datos.
        
        Args:
            data_manager: Gestor de datos de Binance
            market_data_days: Número de días de datos históricos a obtener
        """
        self.data_manager = data_manager
        self.market_data_days = market_data_days
    
    def get_account_balance(self) -> Tuple[Dict[str, Dict[str, Any]], float]:
        """
        Obtiene el balance de la cuenta incluyendo todos los activos.
        
        Returns:
            Tuple con diccionario de activos y balance USDC
        """
        try:
            # Obtener balances de la cuenta
            balances = self.data_manager.get_balance_summary()
            
            # Inicializar variables
            usdc_balance = 0.0
            assets_with_balance = {}
            
            # Procesar los balances
            for asset in balances:
                symbol = asset['asset']
                free_balance = float(asset['free'])
                locked_balance = float(asset['locked'])
                total_balance = free_balance + locked_balance
                
                # Si es USDC, almacenar el balance
                if symbol == 'USDC':
                    usdc_balance = total_balance
                # Si tiene balance, obtener su valor actual
                elif total_balance > 0:
                    # Obtener precio actual
                    symbol_ticker = f"{symbol}USDC"
                    current_price = self.data_manager.get_price(symbol_ticker) or 0
                    
                    # Calcular valor en USDC
                    value_usdc = total_balance * current_price
                    
                    # Solo incluir activos con valor significativo
                    if value_usdc > 0.1:  # Al menos 0.1 USDC de valor
                        assets_with_balance[symbol] = {
                            'symbol': symbol,
                            'balance': total_balance,
                            'free': free_balance,
                            'locked': locked_balance,
                            'current_price': current_price,
                            'value_usdc': value_usdc
                        }
            
            logger.debug(f"Balance de USDC: {usdc_balance}, Activos con balance: {len(assets_with_balance)}")
            return assets_with_balance, usdc_balance
            
        except Exception as e:
            logger.error(f"Error obteniendo balance de cuenta: {e}")
            return {}, 0.0
    
    def get_market_data(self) -> Tuple[List[str], Dict[str, pd.DataFrame]]:
        """
        Obtiene datos históricos de precio para los símbolos activos.
        
        Returns:
            Tuple con lista de símbolos válidos y diccionario de datos históricos
        """
        try:
            # Obtener las criptomonedas más populares como base para el portafolio
            most_popular = self.data_manager.get_most_popular(limit=30)  # Top 30 por volumen
            
            # Filtrar y convertir al formato deseado
            usdc_symbols = []
            for ticker in most_popular:
                if 'symbol' in ticker and ticker['symbol'].endswith('USDC'):
                    symbol = ticker['symbol'].replace('USDC', '')
                    usdc_symbols.append(symbol)
                
            # Añadir también las de mayor capitalización
            try:
                top_market_cap = self.data_manager.get_top_cryptocurrencies(top_n=20)
                for ticker in top_market_cap:
                    if 'symbol' in ticker and ticker['symbol'].endswith('USDC'):
                        symbol = ticker['symbol'].replace('USDC', '')
                        if symbol not in usdc_symbols:
                            usdc_symbols.append(symbol)
            except Exception as e:
                logger.debug(f"Error obteniendo top cryptocurrencies: {e}")
            
            # Si la lista está vacía, usar una lista predefinida de las principales crypto
            if not usdc_symbols:
                usdc_symbols = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'AVAX', 'DOT', 'MATIC', 'LINK']
                logger.warning(f"Usando lista de símbolos predefinida: {usdc_symbols}")
            
            # Obtener datos históricos
            price_data = {}
            for symbol in usdc_symbols:
                try:
                    ticker = f"{symbol}USDC"
                    # Calcular tiempo de inicio (aproximadamente self.market_data_days atrás)
                    end_time = int(datetime.now().timestamp() * 1000)
                    start_time = end_time - (self.market_data_days * 24 * 60 * 60 * 1000)
                    
                    klines = self.data_manager.fetch_historical_data(
                        symbol=ticker,
                        interval='1d',
                        start_time=start_time,
                        end_time=end_time,
                        limit=self.market_data_days
                    )
                    
                    # Convertir a dataframe si aún no lo es (a veces viene como lista de listas)
                    if isinstance(klines, list) and len(klines) > 0 and isinstance(klines[0], list):
                        # Formato: [[time, open, high, low, close, vol, close_time, ...], ...]
                        df = pd.DataFrame(klines, columns=[
                            'open_time', 'open', 'high', 'low', 'close', 'volume',
                            'close_time', 'quote_volume', 'trades_count', 'taker_buy_volume',
                            'taker_buy_quote_volume', 'ignore'
                        ])
                        
                        # Convertir tipos de datos
                        for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume']:
                            df[col] = df[col].astype(float)
                            
                    # Verificar que haya suficientes datos
                    if len(df) > 10:
                        price_data[symbol] = df
                except Exception as e:
                    logger.debug(f"Error obteniendo datos para {symbol}: {e}")
            
            # Si no se obtuvieron datos, usar la lista predefinida de cryptos más sólidas
            if not price_data:
                logger.warning("No se obtuvieron datos de mercado. Usando asignación predeterminada.")
                # Podemos devolver la lista predefinida como fallback
                return usdc_symbols, {"default": pd.DataFrame()}
            
            valid_symbols = list(price_data.keys())
            logger.info(f"Obtenidos datos históricos para {len(valid_symbols)} símbolos")
            
            return valid_symbols, price_data
            
        except Exception as e:
            logger.error(f"Error obteniendo datos de mercado: {e}")
            return [], {}
    
    def update_portfolio_state(self, state: PortfolioState) -> bool:
        """
        Actualiza el estado del portafolio con los datos más recientes.
        
        Args:
            state: Estado actual del portafolio a actualizar
            
        Returns:
            bool: True si la actualización fue exitosa, False en caso contrario
        """
        try:
            # Obtener balance de cuenta
            assets, usdc_balance = self.get_account_balance()
            
            # Calcular valor total del portafolio
            total_value = usdc_balance
            for symbol, asset in assets.items():
                total_value += asset['value_usdc']
            
            # Actualizar estado del portafolio
            state.current_assets = assets
            state.usdc_balance = usdc_balance
            state.total_value = total_value
            
            # Calcular asignación actual
            current_allocation = {}
            for symbol, asset in assets.items():
                if total_value > 0:
                    current_allocation[symbol] = asset['value_usdc'] / total_value
                else:
                    current_allocation[symbol] = 0
            
            # Incluir USDC en la asignación
            if total_value > 0:
                current_allocation['USDC'] = usdc_balance / total_value
            else:
                current_allocation['USDC'] = 1.0
                
            state.current_allocation = current_allocation
            
            # Obtener datos de mercado si es necesario
            valid_symbols, market_data = self.get_market_data()
            
            state.valid_symbols = valid_symbols
            state.market_data = market_data
            
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando estado del portafolio: {e}")
            return False
