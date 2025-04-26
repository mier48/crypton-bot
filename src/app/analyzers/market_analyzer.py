import pandas as pd
import logging
from config.default import (
    SMA_SHORT_PERIOD, SMA_LONG_PERIOD, EMA_PERIOD, RSI_PERIOD,
    MACD_SHORT_PERIOD, MACD_LONG_PERIOD, MACD_SIGNAL_PERIOD,
    BB_PERIOD, BB_STD_DEV, ADX_PERIOD, STOCHASTIC_PERIOD,
    BUY_THRESHOLD_SMA, BUY_THRESHOLD_RSI, BUY_THRESHOLD_MACD,
    BUY_THRESHOLD_BB, BUY_THRESHOLD_ADX, BUY_THRESHOLD_STOCHASTIC,
    DEFAULT_VALIDATION_MIN_SCORE as MIN_SCORE,
    BUBBLE_DETECT_WINDOW, BUBBLE_MAX_GROWTH
)
from utils.logger import setup_logger

logger = setup_logger()

class MarketAnalyzer:
    """
    Analizador de mercado para criptomonedas basado en múltiples indicadores técnicos.
    Usa parámetros definidos en config.default.
    """

    def __init__(self, data, symbol):
        """
        Inicializa el analizador de mercado con los datos de precios provenientes de Binance.

        :param data: Lista de listas con datos de Kline de Binance.
        """
        if not data or len(data) < SMA_LONG_PERIOD:
            raise ValueError("Datos insuficientes para realizar el análisis.")

        self.data = data
        self.close_prices = pd.Series([float(kline[4]) for kline in data])
        self.timestamps = pd.to_datetime([kline[0] for kline in data], unit='ms')
        self.volume = pd.Series([float(kline[5]) for kline in data])
        self.high = pd.Series([float(kline[2]) for kline in data])
        self.low = pd.Series([float(kline[3]) for kline in data])
        self.symbol = symbol
        
        self.df = pd.DataFrame({
            'close': self.close_prices,
            'volume': self.volume,
            'high': self.high,
            'low': self.low,
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
        self._calculate_adx()
        self._calculate_stochastic()
        self._calculate_volume()
        # Limpiar NaNs resultantes del cálculo de indicadores
        self.df.dropna(inplace=True)
        # Opcional: almacenar indicadores disponibles
        self.indicators = self.df.copy()

    def _calculate_sma(self):
        """Calcula las Medias Móviles Simples (SMA)."""
        self.df['sma_short'] = self.df['close'].rolling(window=SMA_SHORT_PERIOD).mean()
        self.df['sma_long'] = self.df['close'].rolling(window=SMA_LONG_PERIOD).mean()
        logger.debug("SMA calculadas.")

    def _calculate_ema(self):
        """Calcula la Media Móvil Exponencial (EMA)."""
        self.df['ema'] = self.df['close'].ewm(span=EMA_PERIOD, adjust=False).mean()
        logger.debug("EMA calculada.")

    def _calculate_rsi(self):
        """Calcula el Índice de Fuerza Relativa (RSI)."""
        delta = self.df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
        rs = gain / loss
        self.df['rsi'] = 100 - (100 / (1 + rs))
        logger.debug("RSI calculado.")

    def _calculate_macd(self):
        """Calcula el MACD y su línea de señal."""
        self.df['macd'] = self.df['close'].ewm(span=MACD_SHORT_PERIOD, adjust=False).mean() - \
                           self.df['close'].ewm(span=MACD_LONG_PERIOD, adjust=False).mean()
        self.df['macd_signal'] = self.df['macd'].ewm(span=MACD_SIGNAL_PERIOD, adjust=False).mean()
        self.df['macd_hist'] = self.df['macd'] - self.df['macd_signal']
        logger.debug("MACD calculado.")

    def _calculate_bollinger_bands(self):
        """Calcula las Bandas de Bollinger."""
        rolling_mean = self.df['close'].rolling(window=BB_PERIOD).mean()
        rolling_std = self.df['close'].rolling(window=BB_PERIOD).std()
        self.df['bb_upper'] = rolling_mean + (rolling_std * BB_STD_DEV)
        self.df['bb_lower'] = rolling_mean - (rolling_std * BB_STD_DEV)
        logger.debug("Bandas de Bollinger calculadas.")

    def _calculate_adx(self):
        """Calcula el Average Directional Index (ADX)."""
        df = self.df.copy()
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = (df['high'] - df['close'].shift()).abs()
        df['tr3'] = (df['low'] - df['close'].shift()).abs()
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)

        df['+dm'] = df['high'].diff()
        df['-dm'] = -df['low'].diff()
        df['+dm'] = df['+dm'].where((df['+dm'] > df['-dm']) & (df['+dm'] > 0), 0)
        df['-dm'] = df['-dm'].where((df['-dm'] > df['+dm']) & (df['-dm'] > 0), 0)

        df['tr_sum'] = df['tr'].rolling(window=ADX_PERIOD).sum()
        df['+dm_sum'] = df['+dm'].rolling(window=ADX_PERIOD).sum()
        df['-dm_sum'] = df['-dm'].rolling(window=ADX_PERIOD).sum()

        df['+di'] = 100 * (df['+dm_sum'] / df['tr_sum'])
        df['-di'] = 100 * (df['-dm_sum'] / df['tr_sum'])
        df['dx'] = (abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])).fillna(0) * 100
        df['adx'] = df['dx'].rolling(window=ADX_PERIOD).mean()

        self.df['adx'] = df['adx']
        logger.debug("ADX calculado.")

    def _calculate_stochastic(self):
        """Calcula el Oscilador Estocástico."""
        low_min = self.df['close'].rolling(window=STOCHASTIC_PERIOD).min()
        high_max = self.df['close'].rolling(window=STOCHASTIC_PERIOD).max()
        self.df['stochastic'] = 100 * (self.df['close'] - low_min) / (high_max - low_min)
        logger.debug("Oscilador Estocástico calculado.")

    def _calculate_volume(self):
        """Calcula el promedio de volumen."""
        self.df['volume_ma'] = self.df['volume'].rolling(window=20).mean()
        logger.debug("Promedio de volumen calculado.")

    def _latest(self):
        """Obtiene los últimos valores de los indicadores."""
        return self.df.iloc[-1]

    def calculate_sell_price(self, latest, profit_margin=0.005):
        """
        Calcula el nivel de precio de venta necesario para alcanzar el margen de beneficio deseado.

        :param latest: Últimos valores de los indicadores.
        :param profit_margin: Margen de beneficio deseado (por defecto 0.5%).
        :return: Precio de venta necesario.
        """
        sell_price = latest['close'] * (1 + profit_margin)
        logger.debug(f"Precio de venta calculado: {sell_price}")
        return sell_price

    def is_sell_price_valid(self, sell_price, safety_margin=0.855):
        """
        Verifica si el precio de venta necesario es menor que el máximo histórico ajustado por el margen de seguridad.

        :param sell_price: Precio de venta necesario.
        :param safety_margin: Margen de seguridad para el máximo histórico (por defecto 99.5%).
        :return: True si válido, False en caso contrario.
        """
        historical_max = self.df['close'].max()
        adjusted_max = historical_max * safety_margin
        logger.debug(f"Máximo histórico: {historical_max}, Máximo ajustado: {adjusted_max}, Precio de venta necesario: {sell_price}")
        return sell_price <= adjusted_max

    def is_buy_signal(self):
        """
        Determina si hay una señal de compra basada en múltiples indicadores y la validación del precio de venta.

        :return: True si es una señal de compra válida, de lo contrario, False.
        """
        latest = self._latest()
        # Detección de burbuja: evitar compras tras subidas excesivas
        if len(self.df) >= BUBBLE_DETECT_WINDOW:
            prev_price = self.df['close'].iloc[-BUBBLE_DETECT_WINDOW]
            growth = (latest['close'] - prev_price) / prev_price
            if growth > BUBBLE_MAX_GROWTH:
                logger.warning(f"[{self.symbol}] Descarta señal: posible burbuja (crecimiento {growth:.2%} en últimas {BUBBLE_DETECT_WINDOW} velas).")
                return False

        score = 0

        # Condiciones ajustadas
        sma_condition = latest['sma_short'] > latest['sma_long']  # Cruce de SMA
        rsi_condition = latest['rsi'] < BUY_THRESHOLD_RSI  # Sobreventa
        macd_condition = latest['macd_hist'] > BUY_THRESHOLD_MACD  # Histograma MACD positivo
        bb_condition = latest['close'] <= latest['bb_lower']  # En la banda inferior
        adx_condition = latest['adx'] > BUY_THRESHOLD_ADX  # Tendencia fuerte
        stochastic_condition = latest['stochastic'] < BUY_THRESHOLD_STOCHASTIC  # Sobreventa

        # Sumar puntuaciones
        if sma_condition:
            score += 1
            logger.debug("Condición SMA cumplida.")
        if rsi_condition:
            score += 1
            logger.debug("Condición RSI cumplida.")
        if macd_condition:
            score += 1
            logger.debug("Condición MACD cumplida.")
        if bb_condition:
            score += 1
            logger.debug("Condición Bandas de Bollinger cumplida.")
        if adx_condition:
            score += 1
            logger.debug("Condición ADX cumplida.")
        if stochastic_condition:
            score += 1
            logger.debug("Condición Oscilador Estocástico cumplida.")

        # if score >= 4:
        logger.info(f"[{self.symbol}] Puntuación total: {score} (Umbral requerido: {MIN_SCORE})")

        # Verificar si se cumple el MIN_SCORE
        if score >= MIN_SCORE:
            logger.info(f"[{self.symbol}] Señal de compra detectada ({score} / {MIN_SCORE} puntos).")
            # Calcular el precio de venta necesario
            sell_price = self.calculate_sell_price(latest)
            # Validar el precio de venta
            if self.is_sell_price_valid(sell_price):
                logger.info("Señal de compra válida detectada.")
                return True
            else:
                logger.info(f"[{self.symbol}] Señal de compra descartada: El precio de venta necesario excede el máximo histórico ajustado.")
                return False
        else:
            return False

    def analyze(self):
        """
        Analiza el mercado y proporciona una recomendación.

        :return: True si es una buena oportunidad de compra, de lo contrario, False.
        """
        try:
            if self.is_buy_signal():
                logger.info(f"[{self.symbol}] Recomendación: Comprar.\n")
                return True
            else:
                logger.info(f"[{self.symbol}] Recomendación: No comprar.\n")
                return False
        except Exception as e:
            logger.error(f"[{self.symbol}] Error en el análisis: {e}")
            return False

    def get_signals(self):
        """
        Obtiene las condiciones actuales de los indicadores.

        :return: Tuple con el estado de cada condición.
        """
        latest = self._latest()

        sma_condition = latest['sma_short'] > latest['sma_long']
        rsi_condition = latest['rsi'] < BUY_THRESHOLD_RSI
        macd_condition = latest['macd_hist'] > BUY_THRESHOLD_MACD
        bb_condition = latest['close'] <= latest['bb_lower']
        adx_condition = latest['adx'] > BUY_THRESHOLD_ADX
        stochastic_condition = latest['stochastic'] < BUY_THRESHOLD_STOCHASTIC

        return sma_condition, rsi_condition, macd_condition, bb_condition, adx_condition, stochastic_condition

    def calculate_stop_loss(self, latest, percentage=0.02):
        """
        Calcula el nivel de stop-loss.

        :param latest: Últimos valores de los indicadores.
        :param percentage: Porcentaje de pérdida máxima aceptable.
        :return: Precio de stop-loss.
        """
        stop_loss = latest['close'] * (1 - percentage)
        logger.info(f"Stop-Loss calculado en: {stop_loss}")
        return stop_loss

    def calculate_take_profit(self, latest, percentage=0.05):
        """
        Calcula el nivel de take-profit.

        :param latest: Últimos valores de los indicadores.
        :param percentage: Porcentaje de ganancia objetivo.
        :return: Precio de take-profit.
        """
        take_profit = latest['close'] * (1 + percentage)
        logger.info(f"Take-Profit calculado en: {take_profit}")
        return take_profit
