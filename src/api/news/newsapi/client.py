from api.news.base_news_api import BaseNewsAPI
from config.newsapi import NEWS_API_API_KEY, BASE_URL, LANGUAGE, PAGE_SIZE

class NewsAPIClient(BaseNewsAPI):    
    def __init__(self, language=LANGUAGE, page_size=PAGE_SIZE):
        """
        Inicializa el cliente de NewsAPI.
        """
        super().__init__()
        self.base_url = BASE_URL
        self.language = language
        self.page_size = page_size

    def fetch_articles(self, keyword):
        """
        Obtiene artículos de noticias relacionados con una palabra clave.
        :param keyword: Palabra clave a buscar.
        :param language: Idioma de los resultados (por defecto, inglés).
        :param page_size: Número máximo de resultados por página.
        :return: Lista de artículos en formato JSON.
        """
        url = f"{self.base_url}everything"
        params = {
            "q": keyword,
            "language": self.language,
            "pageSize": self.page_size,
            "apiKey": NEWS_API_API_KEY
        }

        response = self.send_request(url, params=params)
        if response:
            return response.get("articles", [])
        else:
            raise Exception("Error al recuperar publicaciones de News Api.")
