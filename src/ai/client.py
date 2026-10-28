import json
import os
import re

import requests


class AIConfigurationError(RuntimeError):
    pass


class AIResponseError(RuntimeError):
    pass


class GenerativeAIClient:
    """Client for a configured OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        endpoint=None,
        model=None,
        api_key=None,
        timeout=15,
    ):
        self.endpoint = endpoint or os.getenv("GENAI_API_URL", "").strip()
        self.model = model or os.getenv("GENAI_MODEL", "").strip()
        self.api_key = api_key or os.getenv("GENAI_API_KEY", "").strip()
        self.timeout = timeout

    @property
    def is_configured(self):
        return bool(self.endpoint and self.model and self.api_key)

    def generate_scenario(self, instruction):
        if not self.is_configured:
            raise AIConfigurationError(
                "La IA no está configurada. Definir GENAI_API_URL, GENAI_MODEL "
                "y GENAI_API_KEY; usar escenarios locales mientras tanto."
            )
        if not instruction.strip():
            raise ValueError("Escribe una instrucción antes de enviarla.")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Interpreta la solicitud como un escenario de evacuación. "
                        "Devuelve únicamente un objeto JSON con emergency_type "
                        "(incendio, zona_peligrosa, salida_bloqueada o combinada), "
                        "zone (una zona válida del mapa), people (opcional, entero "
                        "de 1 a 24; por omisión 24) y blocked_exits (opcional, "
                        "lista de A, B, C, D o norte, sur, este, oeste). "
                        "Zonas válidas: Laboratorio, Aula 1, Aula 2, "
                        "Oficina, Biblioteca, Aula 3, Aula 4, Sala, Pasillo central. "
                        "No incluyas campos adicionales ni calcules rutas."
                    ),
                },
                {"role": "user", "content": instruction},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.Timeout as error:
            raise AIResponseError("La solicitud a la IA excedió el tiempo límite.") from error
        except requests.RequestException as error:
            raise AIResponseError(f"No se pudo conectar con la API de IA: {error}") from error

        if not response.ok:
            raise AIResponseError(
                f"La API de IA respondió HTTP {response.status_code}."
            )
        try:
            body = response.json()
        except requests.exceptions.JSONDecodeError as error:
            raise AIResponseError("La API devolvió una respuesta que no es JSON.") from error

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise AIResponseError(
                "La respuesta de la API no tiene el formato chat-completions esperado."
            ) from error
        if not isinstance(content, str) or not content.strip():
            raise AIResponseError("La API devolvió una respuesta vacía.")

        content = content.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        if fenced:
            content = fenced.group(1)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise AIResponseError("La IA no devolvió un objeto JSON válido.") from error
        if not isinstance(parsed, dict):
            raise AIResponseError("La respuesta JSON de la IA debe ser un objeto.")
        return parsed
