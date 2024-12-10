import requests

class BaseNewsAPI:
    def __init__(self):
        pass
    
    def send_request(self, url, params=None, headers=None):
        """
        Envía una solicitud HTTP a la API de Reddit.
        :param url: URL del endpoint.
        :param params: Parámetros de consulta.
        :param headers: Encabezados de la solicitud.
        :return: Respuesta en formato JSON.
        """
        response = requests.get(url, params=params, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error en la solicitud: {response.status_code} - {response.text}")
