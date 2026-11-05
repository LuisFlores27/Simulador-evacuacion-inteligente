import json
import os
import re
import unicodedata

import requests

from emergency.scenario import ZONE_CELLS


class AIConfigurationError(RuntimeError):
    pass


class AIResponseError(RuntimeError):
    pass


class GenerativeAIClient:
    """Client for a configured OpenAI-compatible chat-completions endpoint."""

    DEFAULT_ENDPOINT = "http://localhost:11434/v1/chat/completions"
    DEFAULT_MODEL = "llama3.2"

    def __init__(
        self,
        endpoint=None,
        model=None,
        api_key=None,
        timeout=120,
    ):
        self.endpoint = (
            endpoint.strip()
            if endpoint is not None
            else os.getenv("GENAI_API_URL", "").strip()
            or self.DEFAULT_ENDPOINT
        )
        self.model = (
            model.strip()
            if model is not None
            else os.getenv("GENAI_MODEL", "").strip()
            or self.DEFAULT_MODEL
        )
        self.api_key = api_key or os.getenv("GENAI_API_KEY", "").strip()
        self.timeout = timeout

    @property
    def is_configured(self):
        return bool(self.endpoint and self.model)

    @staticmethod
    def validate_instruction(instruction):
        if not isinstance(instruction, str):
            raise ValueError("La instrucción debe ser texto.")

        normalized = unicodedata.normalize("NFKD", instruction.casefold())
        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        if not normalized.strip():
            raise ValueError("Escribe una instrucción antes de enviarla.")

        emergency_pattern = re.compile(
            r"\b(?:incendi\w*|fueg\w*|hum(?:o|ared\w*)|terremot\w*|"
            r"sism\w*|tembl\w*|derrumbe\w*|escombro\w*|peligro\w*|"
            r"riesgo\w*|evacua\w*|atrapad\w*|colaps\w*)\b"
        )
        exit_blocking_pattern = re.compile(
            r"\b(?:bloque\w*|obstru\w*|cerr\w*)\b.*"
            r"\b(?:salidas?|puertas?)\b|"
            r"\b(?:salidas?|puertas?)\b.*\b(?:bloque\w*|obstru\w*|cerr\w*)\b"
        )
        if not (
            emergency_pattern.search(normalized)
            or exit_blocking_pattern.search(normalized)
        ):
            raise ValueError(
                "La instrucción no describe una emergencia reconocible. "
                "Menciona un incendio, terremoto, peligro, evacuación o salida bloqueada."
            )

    @staticmethod
    def _explicit_floor_counts(instruction):
        floor_pattern = (
            r"(?P<floor>primer(?:o|a)?(?:\s+piso)?|"
            r"segund[oa](?:\s+piso)?|piso\s*[12]|"
            r"[12](?:er|ro|do)?\s+piso)"
        )
        count_pattern = r"(?P<count>\d+)\s*(?:personas?)?"
        patterns = (
            re.compile(
                count_pattern
                + r"\s*(?:en\s+(?:el\s+)?)?"
                + floor_pattern,
                re.IGNORECASE,
            ),
            re.compile(
                floor_pattern
                + r"\s*(?:con|:|,)?\s*"
                + count_pattern,
                re.IGNORECASE,
            ),
        )
        counts = {}
        for pattern in patterns:
            for match in pattern.finditer(instruction):
                floor_text = match.group("floor").casefold()
                floor = (
                    1
                    if floor_text.startswith("primer")
                    or re.search(r"\b1\b", floor_text)
                    else 2
                )
                counts[floor] = int(match.group("count"))
        if len(counts) < 2:
            return None
        return {str(floor): counts.get(floor, 0) for floor in (1, 2)}

    @staticmethod
    def _instruction_specifies_people(instruction):
        explicit_floor_counts = GenerativeAIClient._explicit_floor_counts(
            instruction
        )
        if explicit_floor_counts is not None:
            return True

        normalized = unicodedata.normalize("NFKD", instruction.casefold())
        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        count_pattern = re.compile(
            r"\b\d+\s*(?:personas?|individuos?|ocupantes?)\b|"
            r"\b(?:personas?|individuos?|ocupantes?)\s*(?:son|:)?\s*\d+\b|"
            r"\b\d+\s+en\s+total\b"
        )
        return bool(count_pattern.search(normalized))

    @staticmethod
    def _explicit_danger_zones(instruction):
        zone_patterns = (
            ("Laboratorio", r"\blaboratorios?\b|\blaborios?\b"),
            ("Aula 1", r"\baulas?\s*1\b"),
            ("Aula 2", r"\baulas?\s*2\b"),
            ("Oficina", r"\boficinas?\b"),
            ("Biblioteca", r"\bbibliotecas?\b"),
            ("Aula 3", r"\baulas?\s*3\b"),
            ("Aula 4", r"\baulas?\s*4\b"),
            ("Sala", r"\bsalas?\b"),
            ("Pasillo central", r"\bpasillos?\s+centrales?\b"),
        )
        floor_pattern = re.compile(
            r"\bpri(?:u)?mer[oa]?(?:\s+piso)?\b|"
            r"\bsegund[oa](?:\s+piso)?\b|"
            r"\bpiso\s*[12]\b|"
            r"\b[12](?:er|do|ro)\s+piso\b",
            re.IGNORECASE,
        )
        danger_pattern = re.compile(
            r"\b(?:peligros?\w*|riesgos?\w*|escombros?|derrumb\w*|"
            r"inestables?\w*|dañad\w*)\b",
            re.IGNORECASE,
        )
        danger_zones = []
        for sentence in re.split(r"[.!?;\n]", instruction):
            if not danger_pattern.search(sentence):
                continue
            floors = set()
            for match in floor_pattern.finditer(sentence):
                floor_text = match.group().casefold()
                floor = (
                    1
                    if floor_text.startswith(("primer", "priumer"))
                    or re.search(r"\b1\b", floor_text)
                    else 2
                )
                floors.add(floor)
            if not floors:
                continue
            for zone, pattern in zone_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    for floor in sorted(floors):
                        entry = {"zone": zone, "floor": floor}
                        if entry not in danger_zones:
                            danger_zones.append(entry)
        return danger_zones

    @staticmethod
    def _explicit_full_floor_fire_zones(instruction):
        normalized = unicodedata.normalize("NFKD", instruction.casefold())
        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        fire_pattern = re.compile(r"\b(?:incendi\w*|fueg\w*|llama\w*)\b")
        floor_expression = (
            r"primer(?:o|a)?(?:\s+piso)?|"
            r"segund[oa](?:\s+piso)?|"
            r"piso\s*[12]|"
            r"[12](?:er|do|ro)\s+piso"
        )
        named_full_floor_patterns = (
            re.compile(
                rf"\b(?:todo|toda|todos|todas)\s+"
                rf"(?:(?:el|la|los|las)\s+)?"
                rf"(?P<floor>{floor_expression})\b"
            ),
            re.compile(
                rf"\b(?P<floor>{floor_expression})\s+"
                r"(?:complet\w*|enter\w*)\b"
            ),
        )
        floor_pattern = re.compile(rf"\b({floor_expression})\b")
        both_floors_pattern = re.compile(
            r"\b(?:ambos|ambas)\s+(?:los\s+)?pisos\b|"
            r"\btodos\s+los\s+pisos\b"
        )
        generic_full_floor_pattern = re.compile(
            r"\b(?:todo|toda)\s+(?:el\s+)?piso\b|"
            r"\bpiso\s+(?:complet\w*|enter\w*)\b"
        )

        def floor_number(floor_text):
            return (
                1
                if floor_text.startswith(("primer", "priumer"))
                or re.search(r"\b1\b", floor_text)
                else 2
            )

        fire_zones = []

        for sentence in re.split(r"[.!?;\n]", normalized):
            if not fire_pattern.search(sentence):
                continue
            floors = {
                floor_number(match.group("floor"))
                for pattern in named_full_floor_patterns
                for match in pattern.finditer(sentence)
            }
            if both_floors_pattern.search(sentence):
                floors.update((1, 2))
            elif (
                not floors
                and generic_full_floor_pattern.search(sentence)
            ):
                mentioned_floors = {
                    floor_number(match.group())
                    for match in floor_pattern.finditer(sentence)
                }
                if len(mentioned_floors) == 1:
                    floors.update(mentioned_floors)

            for floor in sorted(floors):
                for zone in ZONE_CELLS:
                    entry = {
                        "zone": " ".join(
                            word.capitalize() for word in zone.split()
                        ),
                        "floor": floor,
                    }
                    if entry not in fire_zones:
                        fire_zones.append(entry)

        return fire_zones

    @staticmethod
    def _explicitly_requests_blocked_exits(instruction):
        action_pattern = re.compile(
            r"\b(?:bloque\w*|obstru\w*|cierre|cerr\w*)\b",
            re.IGNORECASE,
        )
        exit_pattern = re.compile(r"\b(?:salidas?|puertas?)\b", re.IGNORECASE)
        for sentence in re.split(r"[.!?;\n]", instruction):
            for action in action_pattern.finditer(sentence):
                if not any(
                    abs(action.start() - exit_match.start()) <= 50
                    for exit_match in exit_pattern.finditer(sentence)
                ):
                    continue
                preceding_text = sentence[:action.start()]
                if re.search(
                    r"\b(?:no|nunca|sin)\b.{0,24}$",
                    preceding_text,
                    re.IGNORECASE,
                ):
                    continue
                return True
        return False

    @staticmethod
    def _explicit_open_only_exits(instruction):
        normalized = unicodedata.normalize("NFKD", instruction.casefold())
        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        exclusive_pattern = re.compile(
            r"\b(?:solo|solamente|unicamente)\b"
        )
        open_pattern = re.compile(
            r"\b(?:abiert\w*|disponible\w*|libre\w*)\b"
        )
        exit_pattern = re.compile(r"\b(?:salidas?|puertas?)\b")
        direction_exits = {
            "norte": "C",
            "sur": "D",
            "este": "B",
            "oeste": "A",
        }
        open_exits = set()

        for sentence in re.split(r"[.!?;\n]", normalized):
            if not (
                exclusive_pattern.search(sentence)
                and open_pattern.search(sentence)
                and exit_pattern.search(sentence)
            ):
                continue
            for direction, identifier in direction_exits.items():
                if re.search(rf"\b{direction}\b", sentence):
                    open_exits.add(identifier)
            for match in re.finditer(
                r"\b(?:salidas?|puertas?)\s+(?:letra\s+)?([abcd])\b",
                sentence,
            ):
                open_exits.add(match.group(1).upper())

        return open_exits or None

    def generate_scenario(self, instruction):
        if not self.is_configured:
            raise AIConfigurationError(
                "La IA no está configurada. Definir GENAI_API_URL, GENAI_MODEL "
                "; GENAI_API_KEY es opcional para servicios que no la requieren."
            )
        self.validate_instruction(instruction)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Interpreta la solicitud como un escenario de evacuación. "
                        "Devuelve únicamente un objeto JSON. Las claves "
                        "obligatorias son emergency_type, zone y floor; las "
                        "opcionales son people, people_by_floor, blocked_exits, "
                        "danger_zones y fire_zones. No omitas datos que el usuario "
                        "especificó. emergency_type "
                        "(incendio, terremoto, zona_peligrosa, salida_bloqueada "
                        "o combinada), "
                        "zone (una zona válida del mapa), floor (1 o 2, según el "
                        "piso indicado; usa 1 si no se especifica). Incluye "
                        "people_by_floor como objeto con claves '1' y '2' y "
                        "cantidades enteras cuando el usuario especifique personas "
                        "por piso (por ejemplo {\"1\":8,\"2\":4}). Respeta "
                        "exactamente las cantidades indicadas; no las intercambies "
                        "ni inventes cantidades. Si no se especifica una cantidad, "
                        "no inventes una: usa people=24 como valor predeterminado. "
                        "Nunca generes más de 80 personas. El total debe ser de 1 a 80. "
                        "Si solo indica un total, usa people "
                        "(entero de 1 a 80) y floor para ubicarlas. "
                        "blocked_exits (opcional, lista de A, B, C, D o norte, "
                        "sur, este, oeste; inclúyela únicamente si el usuario "
                        "pide explícitamente bloquear salidas. Si pide dejar "
                        "abiertas solo algunas, incluye las demás en "
                        "blocked_exits). Para incendio en todo un piso, "
                        "incluye todas las zonas afectadas en fire_zones con "
                        "zone y floor; deben quedar como fuego, no solo peligro. "
                        "danger_zones "
                        "(opcional, lista de objetos con zone y floor; ejemplo: "
                        "[{\"zone\":\"Laboratorio\",\"floor\":2}]). Cada objeto "
                        "representa una zona peligrosa en ese piso. Si la misma "
                        "zona es peligrosa en ambos pisos, incluye dos objetos "
                        "con floors 1 y 2. En terremotos usa "
                        "emergency_type='terremoto'. "
                        "Zonas válidas: Laboratorio, Aula 1, Aula 2, "
                        "Oficina, Biblioteca, Aula 3, Aula 4, Sala, Pasillo central. "
                        "Las salidas están en el primer piso. No incluyas campos "
                        "adicionales ni calcules rutas."
                    ),
                },
                {"role": "user", "content": instruction},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

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
        explicitly_open_exits = self._explicit_open_only_exits(instruction)
        if explicitly_open_exits is not None:
            parsed["blocked_exits"] = [
                identifier
                for identifier in ("A", "B", "C", "D")
                if identifier not in explicitly_open_exits
            ]
        elif not self._explicitly_requests_blocked_exits(instruction):
            parsed.pop("blocked_exits", None)
            if parsed.get("emergency_type") in {"salida_bloqueada", "combinada"}:
                parsed["emergency_type"] = "zona_peligrosa"
        explicit_counts = self._explicit_floor_counts(instruction)
        if explicit_counts is not None:
            parsed["people_by_floor"] = explicit_counts
        elif not self._instruction_specifies_people(instruction):
            parsed.pop("people_by_floor", None)
            parsed["people"] = 24
        if re.search(
            r"\b(terremoto|temblor|temblando|sismo|sismico|sísmico)\b",
            instruction,
            re.IGNORECASE,
        ):
            parsed["emergency_type"] = "terremoto"
        explicit_danger_zones = self._explicit_danger_zones(instruction)
        if parsed["emergency_type"] == "terremoto" and explicit_danger_zones:
            parsed["zone"] = explicit_danger_zones[0]["zone"]
            parsed["floor"] = explicit_danger_zones[0]["floor"]
            parsed["danger_zones"] = explicit_danger_zones[1:]
        full_floor_fire_zones = self._explicit_full_floor_fire_zones(
            instruction
        )
        if full_floor_fire_zones:
            parsed["emergency_type"] = "incendio"
            parsed["zone"] = full_floor_fire_zones[0]["zone"]
            parsed["floor"] = full_floor_fire_zones[0]["floor"]
            parsed["fire_zones"] = full_floor_fire_zones
        return parsed
