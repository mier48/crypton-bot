# src/config/openai.py

import os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MODEL = "gpt-4"
TOKENIZER_MODEL="gpt2"