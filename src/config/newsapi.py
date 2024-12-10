import os
from dotenv import load_dotenv

# Cargar el archivo .env
load_dotenv()

NEWS_API_API_KEY = os.getenv("NEWS_API_API_KEY")
BASE_URL = "https://newsapi.org/v2/"
LANGUAGE = "en"
PAGE_SIZE = 100