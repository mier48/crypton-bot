# src/api/openai/client.py

from openai import OpenAI
from transformers import GPT2Tokenizer
from utils.logger import setup_logger
from config.openai import OPENAI_API_KEY, MODEL, TOKENIZER_MODEL
from typing import Optional

# Configuración del logger
logger = setup_logger()

class OpenAIClient:
    def __init__(self, model: str = MODEL, tokenizer_model: str = TOKENIZER_MODEL) -> None:
        """
        Inicializa el cliente para interactuar con la API de OpenAI.
        :param model: Modelo por defecto (e.g., "gpt-4").
        :param tokenizer_model: Modelo del tokenizador.
        """
        if not OPENAI_API_KEY:
            raise ValueError("La clave de API de OpenAI no está configurada.")
        
        self.api_key = OPENAI_API_KEY
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.tokenizer_model = tokenizer_model
        logger.info(f"Cliente inicializado con modelo '{self.model}'.")

    def _validate_prompt_length(self, prompt: str) -> bool:
        """
        Valida si el prompt no excede el límite de tokens permitido.
        :param prompt: El mensaje a validar.
        :return: True si el prompt es válido, False si excede el límite.
        """
        try:
            tokenizer = GPT2Tokenizer.from_pretrained(self.tokenizer_model)
            num_tokens = len(tokenizer.encode(prompt))
            logger.debug(f"El prompt tiene {num_tokens} tokens.")
            
            if num_tokens >= 8000:  # Límite típico de OpenAI
                logger.error(f"El prompt excede el límite permitido ({num_tokens}/8000 tokens).")
                return False
            return True
        except Exception as e:
            logger.error(f"Error al calcular la longitud del prompt: {e}")
            return False

    def send_prompt(self, prompt: str, system_message: str = "Eres un experto en trading e inversiones de criptomonedas.") -> Optional[str]:
        """
        Envía un prompt a la API de OpenAI.
        :param prompt: El mensaje del usuario.
        :param system_message: Mensaje de contexto para el modelo.
        :return: Respuesta de OpenAI o None si hay error.
        """
        if not self._validate_prompt_length(prompt):
            return None

        try:
            logger.info(f"Enviando prompt al modelo '{self.model}'.")
            
            # Realiza la solicitud a la API
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ]
            )
            response = completion.choices[0].message.content.strip()
            logger.info("Respuesta recibida correctamente.")
            return response
        except OpenAI.APIError as api_error:
            logger.error(f"Error de API: {api_error}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado: {e}")
        return None