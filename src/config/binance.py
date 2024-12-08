# src/config/binance.py

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')
BINANCE_TESTNET_API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')
BINANCE_TESTNET_SECRET_KEY = os.getenv('BINANCE_TESTNET_SECRET_KEY')
BINANCE_BASE_URL = os.getenv('BINANCE_BASE_URL', 'https://api.binance.com')
BINANCE_TESTNET_URL = os.getenv('BINANCE_TESTNET_URL', 'https://testnet.binance.vision')

if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
    raise EnvironmentError("Las claves de API de Binance no están configuradas correctamente en el archivo .env")
