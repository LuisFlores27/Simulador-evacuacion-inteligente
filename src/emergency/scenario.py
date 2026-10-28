import json
import unicodedata


MAX_PEOPLE = 24
EMERGENCY_TYPES = {
    "incendio",
    "zona_peligrosa",
    "salida_bloqueada",
    "combinada",
}

ZONE_CELLS = {
    "laboratorio": (1, 1, 6, 4),
    "aula 1": (8, 1, 7, 4),
    "aula 2": (16, 1, 7, 4),
    "oficina": (24, 1, 5, 4),
    "biblioteca": (1, 12, 6, 5),
    "aula 3": (8, 12, 7, 5),
    "aula 4": (16, 12, 7, 5),
    "sala": (24, 12, 5, 5),
    "pasillo central": (1, 6, 28, 5),
}

EXIT_IDS = {
    "a": (0, 8),
    "b": (29, 8),
    "c": (15, 5),
    "d": (15, 11),
}

EXIT_ALIASES = {
    "norte": "c",
    "sur": "d",
    "oeste": "a",
    "este": "b",
}


def _normalize(value):
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    ).strip()


class EmergencyScenario:
    def __init__(
        self,
        emergency_type,
        zone,
        people=24,
        blocked_exit=None,
        blocked_exits=None,
    ):
        if (
            not isinstance(emergency_type, str)
            or emergency_type not in EMERGENCY_TYPES
        ):
            raise ValueError(f"Tipo de emergencia inválido: {emergency_type}.")
        if not isinstance(zone, str) or _normalize(zone) not in ZONE_CELLS:
            raise ValueError(f"Zona desconocida: {zone}.")
        if type(people) is not int or not 1 <= people <= MAX_PEOPLE:
            raise ValueError(f"La cantidad de personas debe estar entre 1 y {MAX_PEOPLE}.")
        self.emergency_type = emergency_type
        self.zone = zone
        self.people = people
        exits = list(blocked_exits or [])
        if blocked_exit is not None:
            exits.append(blocked_exit)
        canonical_exits = []
        for exit_name in exits:
            if not isinstance(exit_name, str):
                raise ValueError("Cada salida bloqueada debe ser texto.")
            key = _normalize(exit_name)
            key = EXIT_ALIASES.get(key, key)
            if key not in EXIT_IDS:
                raise ValueError(f"Salida desconocida: {exit_name}.")
            canonical_exits.append(key.upper())
        self.blocked_exits = tuple(dict.fromkeys(canonical_exits))
        if emergency_type in {"salida_bloqueada", "combinada"} and not self.blocked_exits:
            raise ValueError(
                f"El tipo {emergency_type} requiere al menos una salida bloqueada."
            )

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("La respuesta de la IA debe ser un objeto JSON.")

        allowed = {"emergency_type", "zone", "people", "blocked_exits"}
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(
                "La configuración contiene campos no permitidos: "
                + ", ".join(sorted(unknown))
            )
        if "emergency_type" not in data or "zone" not in data:
            raise ValueError(
                "La configuración requiere 'emergency_type' y 'zone'."
            )

        emergency_type = data["emergency_type"]
        zone = data["zone"]
        people = data.get("people", 24)
        blocked_exits = data.get("blocked_exits", [])

        if not isinstance(emergency_type, str) or emergency_type not in EMERGENCY_TYPES:
            raise ValueError(
                "Tipo de emergencia inválido. Use incendio, zona_peligrosa, "
                "salida_bloqueada o combinada."
            )
        if not isinstance(zone, str) or _normalize(zone) not in ZONE_CELLS:
            raise ValueError(
                "Zona desconocida. Use un nombre de habitación o 'Pasillo central'."
            )
        if type(people) is not int or not 1 <= people <= MAX_PEOPLE:
            raise ValueError(
                f"'people' debe ser un entero entre 1 y {MAX_PEOPLE}."
            )
        if not isinstance(blocked_exits, list):
            raise ValueError("'blocked_exits' debe ser una lista de salidas.")
        if any(not isinstance(exit_name, str) for exit_name in blocked_exits):
            raise ValueError("Cada salida bloqueada debe identificarse como texto.")

        resolved_exits = []
        for exit_name in blocked_exits:
            key = _normalize(exit_name)
            key = EXIT_ALIASES.get(key, key)
            if key not in EXIT_IDS:
                raise ValueError(
                    f"Salida desconocida: {exit_name}. Use A, B, C, D "
                    "o norte, sur, este, oeste."
                )
            resolved_exits.append(key.upper())

        return cls(
            emergency_type=emergency_type,
            zone=zone,
            people=people,
            blocked_exits=resolved_exits,
        )

    @classmethod
    def from_json(cls, content):
        try:
            data = json.loads(content)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("La respuesta recibida no contiene JSON válido.") from error
        return cls.from_dict(data)

    def zone_positions(self):
        x, y, width, height = ZONE_CELLS[_normalize(self.zone)]
        return {
            (column, row)
            for row in range(y, y + height)
            for column in range(x, x + width)
        }

    def blocked_exit_positions(self):
        return {
            EXIT_IDS[_normalize(exit_name)]
            for exit_name in self.blocked_exits
        }

    def __str__(self):
        return (
            f"Emergencia: {self.emergency_type}\n"
            f"Zona afectada: {self.zone}\n"
            f"Personas: {self.people}\n"
            f"Salidas bloqueadas: {', '.join(self.blocked_exits) or 'ninguna'}"
        )
