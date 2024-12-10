import requests
from api.news.base_news_api import BaseNewsAPI
from config.reddit import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, BASE_URL, TOKEN_URL

class RedditClient(BaseNewsAPI):
    def __init__(self):
        """
        Inicializa el cliente de Reddit.
        """
        super().__init__()
        self.base_url = BASE_URL
        self.token_url = TOKEN_URL
        self.token = self.authenticate()

    def authenticate(self):
        """
        Autentica con la API de Reddit y obtiene el token de acceso.
        :return: Token de acceso.
        """
        auth = requests.auth.HTTPBasicAuth(REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET)
        data = {"grant_type": "client_credentials"}
        headers = {"User-Agent": REDDIT_USER_AGENT}

        response = requests.post(self.token_url, auth=auth, data=data, headers=headers)
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            raise Exception(f"Error en la autenticación: {response.json()}")

    def fetch_posts(self, keyword, limit=100):
        """
        Obtiene publicaciones de Reddit relacionadas con una palabra clave.
        :param keyword: Palabra clave a buscar.
        :param limit: Número máximo de publicaciones a recuperar.
        :return: Lista de publicaciones en formato JSON.
        """
        url = f"{self.base_url}search"
        params = {
            "q": keyword,
            "limit": limit,
            "sort": "relevance",
            "restrict_sr": False  # Cambiar a True si se desea restringir a un subreddit
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": REDDIT_USER_AGENT
        }

        response = self.send_request(url, params=params, headers=headers)
        if response:
            return response.get("data", {}).get("children", [])
        else:
            raise Exception("Error al recuperar publicaciones de Reddit.")
