from textblob import TextBlob
from app.managers.trends_manager import TrendsManager
from api.openai.client import OpenAIClient
from api.news.newsapi.client import NewsAPIClient
from api.news.reddit.client import RedditClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

class SentimentAnalyzer:
    def __init__(self, precision=1):
        """
        Inicializa el cliente SentimentAnalyzer.
        :param precision: Nivel de precisión (1 = TextBlob, 2 = TextBlob + OpenAI).
        """
        self.openai_client = OpenAIClient()
        self.precision = precision

    def get_overall_sentiment(self, keyword, limit = 100):
        """
        Calcula un puntaje de sentimiento general combinando fuentes.
        :param keyword: Palabra clave para buscar tendencias.
        :return: Puntaje de sentimiento promedio.
        """
        news_api_client = NewsAPIClient(page_size=limit)
        # Instanciar cliente de Reddit para social media
        reddit_client = RedditClient()
        trends_manager = TrendsManager(news_client=news_api_client, reddit_client=reddit_client)
        articles = trends_manager.fetch_trends(keyword, limit=limit)
        sentiments = [
            self._analyze(" ".join(filter(None, [article.get("title"), article.get("description"), article.get("content")])))
            for article in articles if any(key in article for key in ["title", "description", "content"])
        ]

        if sentiments:
            return sum(sentiments) / len(sentiments)
        else:
            logger.error("No se pudo analizar el sentimiento.")
            return 0

    def _analyze(self, text):
        """
        Combina los resultados de diferentes analizadores para calcular un puntaje promedio.
        :param text: Texto a analizar.
        :return: Promedio de puntajes de sentimiento.
        """
        if self.precision == 1:
            return self._textblob_analyzer(text)
        elif self.precision == 2:
            score1 = self._textblob_analyzer(text)
            score2 = self._openai_analyzer(text)
            return (score1 + score2) / 2
        else:
            raise ValueError("Precisión no válida. Usa 1 (básico) o 2 (combinado).")

    def _textblob_analyzer(self, text):
        """
        Analiza el sentimiento de un texto usando TextBlob.
        :param text: Texto a analizar.
        :return: Puntaje de sentimiento (-1 a 1).
        """
        if not isinstance(text, str) or not text.strip():
            logger.warning("Advertencia: Texto vacío o no válido proporcionado.")
            return 0  # Neutral en caso de entrada inválida

        try:
            analysis = TextBlob(text)
            return analysis.sentiment.polarity
        except Exception as e:
            logger.error(f"Error al analizar el sentimiento con TextBlob: {e}")
            return 0  # Valor predeterminado en caso de error

    def _openai_analyzer(self, text: str):
        """
        Analiza el sentimiento usando OpenAI.
        :param text: Texto a analizar.
        :return: Puntaje de sentimiento (-1 a 1).
        """
        prompt = (
            "Eres un analista de sentimientos avanzado. A continuación, se te proporciona un texto. "
            "Analiza el sentimiento general del texto y devuelve únicamente un número decimal entre -1 y 1. "
            "Un puntaje de -1 significa muy negativo, 0 significa neutral, y 1 significa muy positivo. "
            "No proporciones explicaciones, solo responde con el número:\n\n"
            f"Texto: {text}"
        )
        response = self.openai_client.send_prompt(prompt)
        try:
            return float(response.strip())
        except (ValueError, AttributeError) as e:
            logger.error(f"Error al procesar la respuesta de OpenAI: {e}")
            return 0  # Valor predeterminado en caso de error
