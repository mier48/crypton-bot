from typing import List, Dict, Any
from api.news.newsapi.client import NewsAPIClient
from api.news.reddit.client import RedditClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

class TrendsManager:
    """
    Gestiona la recuperación y combinación de tendencias desde múltiples fuentes.
    """
    
    def __init__(self, news_client: NewsAPIClient = None, reddit_client: RedditClient = None):
        """
        Inicializa el gestor de tendencias con clientes para las fuentes.

        :param news_client: Instancia de NewsAPIClient. Si no se proporciona, se crea una nueva.
        :param reddit_client: Instancia de RedditClient. Si no se proporciona, se crea una nueva.
        """
        self.news_client = news_client or NewsAPIClient()
        self.reddit_client = reddit_client or RedditClient()

    def fetch_trends(self, keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Recupera tendencias combinando datos de múltiples fuentes.

        :param keyword: Palabra clave a buscar (por ejemplo, una criptomoneda).
        :return: Lista combinada de datos de diferentes fuentes con estructura uniforme.
        """
        combined_data = []
        
        # Recuperar y procesar noticias de NewsAPI
        try:
            news_articles = self.news_client.fetch_articles(keyword)
            logger.info(f"NewsAPI: Se recuperaron {len(news_articles)} artículos relacionados con '{keyword}'.")
            formatted_news = self._format_news(news_articles)
            combined_data.extend(formatted_news)
        except Exception as e:
            logger.error(f"Error al recuperar artículos de NewsAPI para '{keyword}': {e}")

        # Recuperar y procesar publicaciones de Reddit
        try:
            reddit_posts = self.reddit_client.fetch_posts(keyword, limit=limit)
            logger.info(f"Reddit: Se recuperaron {len(reddit_posts)} publicaciones relacionadas con '{keyword}'.")
            formatted_reddit = self._format_reddit(reddit_posts)
            combined_data.extend(formatted_reddit)
        except Exception as e:
            logger.error(f"Error al recuperar publicaciones de Reddit para '{keyword}': {e}")

        logger.debug(f"Datos combinados para '{keyword}': {combined_data}")
        return combined_data

    @staticmethod
    def _format_news(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Estructura los datos de NewsAPI en un formato uniforme.

        :param articles: Lista de artículos de NewsAPI.
        :return: Lista de artículos formateados.
        """
        return [
            {
                "title": article.get("title", "Sin título"),
                "description": article.get("description", "Sin descripción"),
                "content": article.get("content") or article.get("description", ""),
                "source": "NewsAPI"
            }
            for article in articles
        ]

    @staticmethod
    def _format_reddit(posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Estructura los datos de Reddit en un formato uniforme.

        :param posts: Lista de publicaciones de Reddit.
        :return: Lista de publicaciones formateadas.
        """
        return [
            {
                "title": post.get("data", {}).get("title", "Sin título"),
                "description": (post.get("data", {}).get("selftext", "")[:150] + "...") if post.get("data", {}).get("selftext") else "Sin descripción",
                "content": post.get("data", {}).get("selftext", ""),
                "source": "Reddit"
            }
            for post in posts
        ]
