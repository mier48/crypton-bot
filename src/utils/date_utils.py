def interval_to_milliseconds(interval: str) -> int:
        """
        Convierte el intervalo de Binance a milisegundos.

        :param interval: Intervalo de Binance (ejemplo: '1m', '5m', '1h', '1d')
        :return: Duración del intervalo en milisegundos.
        """
        ms = 0
        unit = interval[-1]
        if unit == 'm':
            ms = int(interval[:-1]) * 60 * 1000
        elif unit == 'h':
            ms = int(interval[:-1]) * 60 * 60 * 1000
        elif unit == 'd':
            ms = int(interval[:-1]) * 24 * 60 * 60 * 1000
        elif unit == 'w':
            ms = int(interval[:-1]) * 7 * 24 * 60 * 60 * 1000
        elif unit == 'M':
            ms = int(interval[:-1]) * 30 * 24 * 60 * 60 * 1000  # Aproximado
        else:
            raise ValueError(f"Intervalo desconocido: {interval}")
        return ms