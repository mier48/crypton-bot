import os
from dotenv import load_dotenv

# Cargar el archivo .env
load_dotenv()

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")
BASE_URL = "https://oauth.reddit.com/"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"