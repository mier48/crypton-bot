import pandas as pd
import logging
from config.default import DEFAULT_VALIDATION_MIN_SCORE as MIN_SCORE

class MarketAnalyzer:
    """
    Analizador de mercado para criptomonedas basado en múltiples indicadores técnicos.
    Proporciona una recomendación de compra si se cumplen todas las condiciones favorables.
    """
    
    # Parámetros de los indicadores técnicos
    SHORT_SMA_PERIOD = 10
    LONG_SMA_PERIOD = 50
    EMA_PERIOD = 20
    RSI_PERIOD = 14
    MACD_SHORT_PERIOD = 12
    MACD_LONG_PERIOD = 26
    MACD_SIGNAL_PERIOD = 9
    BB_PERIOD = 20
    BB_STD_DEV = 2
    BUY_THRESHOLD_SMA = 0.001
    BUY_THRESHOLD_RSI = 30  # RSI por debajo de 30 indica sobreventa
    BUY_THRESHOLD_MACD = 0
    BUY_THRESHOLD_BB = 'lower'
    
    def __init__(self, data):
        """
        Inicializa el analizador de mercado con los datos de precios provenientes de Binance.

        :param data: Lista de listas con datos de Kline de Binance.
        """
        if not data or len(data) < self.LONG_SMA_PERIOD:
            raise ValueError("Datos insuficientes para realizar el análisis.")
        
        self.data = data
        self.close_prices = pd.Series([float(kline[4]) for kline in data])
        self.timestamps = pd.to_datetime([kline[0] for kline in data], unit='ms')
        self.df = pd.DataFrame({
            'close': self.close_prices,
            'timestamp': self.timestamps
        })
        self.df.set_index('timestamp', inplace=True)
        self._prepare_indicators()
    
    def _prepare_indicators(self):
        """Calcula todos los indicadores técnicos necesarios."""
        self._calculate_sma()
        self._calculate_ema()
        self._calculate_rsi()
        self._calculate_macd()
        self._calculate_bollinger_bands()
    
    def _calculate_sma(self):
        """Calcula las Medias Móviles Simples (SMA)."""
        self.df['sma_short'] = self.df['close'].rolling(window=self.SHORT_SMA_PERIOD).mean()
        self.df['sma_long'] = self.df['close'].rolling(window=self.LONG_SMA_PERIOD).mean()
        # logging.debug("SMA calculada.")
    
    def _calculate_ema(self):
        """Calcula la Media Móvil Exponencial (EMA)."""
        self.df['ema'] = self.df['close'].ewm(span=self.EMA_PERIOD, adjust=False).mean()
        # logging.debug("EMA calculada.")
    
    def _calculate_rsi(self):
        """Calcula el Índice de Fuerza Relativa (RSI)."""
        delta = self.df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.RSI_PERIOD).mean()
        rs = gain / loss
        self.df['rsi'] = 100 - (100 / (1 + rs))
        # logging.debug("RSI calculado.")
    
    def _calculate_macd(self):
        """Calcula el MACD y su línea de señal."""
        self.df['macd'] = self.df['close'].ewm(span=self.MACD_SHORT_PERIOD, adjust=False).mean() - \
                           self.df['close'].ewm(span=self.MACD_LONG_PERIOD, adjust=False).mean()
        self.df['macd_signal'] = self.df['macd'].ewm(span=self.MACD_SIGNAL_PERIOD, adjust=False).mean()
        self.df['macd_hist'] = self.df['macd'] - self.df['macd_signal']
        # logging.debug("MACD calculado.")
    
    def _calculate_bollinger_bands(self):
        """Calcula las Bandas de Bollinger."""
        rolling_mean = self.df['close'].rolling(window=self.BB_PERIOD).mean()
        rolling_std = self.df['close'].rolling(window=self.BB_PERIOD).std()
        self.df['bb_upper'] = rolling_mean + (rolling_std * self.BB_STD_DEV)
        self.df['bb_lower'] = rolling_mean - (rolling_std * self.BB_STD_DEV)
        # logging.debug("Bandas de Bollinger calculadas.")
    
    def _latest(self):
        """Obtiene los últimos valores de los indicadores."""
        return self.df.iloc[-1]

    def is_buy_signal(self):
        """
        Determina si hay una señal de compra basada en múltiples indicadores, 
        permitiendo señales individuales o ponderadas.
        """
        latest = self._latest()
        score = 0
        
        # Condiciones ajustadas
        sma_condition = (latest['sma_short'] - latest['sma_long']) / latest['sma_long'] > -0.001
        rsi_condition = latest['rsi'] < 50
        macd_condition = latest['macd_hist'] > -0.1  # Permitir pequeñas señales positivas
        bb_condition = latest['close'] <= latest['bb_lower'] or latest['close'] >= latest['bb_upper']
        
        # Sumar puntuaciones
        if sma_condition: score += 1
        if rsi_condition: score += 1
        if macd_condition: score += 1
        if bb_condition: score += 1
        
        # Umbral flexible
        return score >= MIN_SCORE
    
    def analyze(self):
        """
        Analiza el mercado y proporciona una recomendación.

        :return: True si es una buena oportunidad de compra, de lo contrario, False.
        """
        try:
            if self.is_buy_signal():
                return True
            else:
                return False
        except Exception as e:
            logging.error(f"Error en el análisis: {e}")
            return False
