import json
import unicodedata


MAX_PEOPLE = 80
FLOOR_HEIGHT = 18
EMERGENCY_TYPES = {
    "incendio",
    "zona_peligrosa",
    "salida_bloqueada",
    "combinada",
    "terremoto",
}

ZONE_CELLS = {
    "laboratorio": (1, 1, 6, 4),
    "aula 1": (8, 1, 5, 4),
    "aula 2": (16, 1, 7, 4),
    "oficina": (24, 1, 5, 4),
    "biblioteca": (1, 12, 6, 5),
    "aula 3": (8, 12, 5, 5),
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
        floor=1,
        people_by_floor=None,
        danger_zones=None,
        fire_zones=None,
    ):
        if (
            not isinstance(emergency_type, str)
            or emergency_type not in EMERGENCY_TYPES
        ):
            raise ValueError(f"Tipo de emergencia inválido: {emergency_type}.")
        if not isinstance(zone, str) or _normalize(zone) not in ZONE_CELLS:
            raise ValueError(f"Zona desconocida: {zone}.")
        if people_by_floor is None:
            if type(people) is not int or not 1 <= people <= MAX_PEOPLE:
                raise ValueError(
                    f"La cantidad de personas debe estar entre 1 y {MAX_PEOPLE}."
                )
            self.people_by_floor = None
        else:
            if not isinstance(people_by_floor, dict):
                raise ValueError("'people_by_floor' debe ser un objeto por piso.")
            if set(people_by_floor) - {"1", "2"}:
                raise ValueError("'people_by_floor' solo admite las claves '1' y '2'.")
            counts = {
                str(floor_number): people_by_floor.get(str(floor_number), 0)
                for floor_number in (1, 2)
            }
            if any(
                type(count) is not int or not 0 <= count <= MAX_PEOPLE
                for count in counts.values()
            ):
                raise ValueError(
                    f"Cada cantidad por piso debe ser un entero de 0 a {MAX_PEOPLE}."
                )
            people = sum(counts.values())
            if not 1 <= people <= MAX_PEOPLE:
                raise ValueError(
                    f"El total de personas debe estar entre 1 y {MAX_PEOPLE}."
                )
            self.people_by_floor = {
                int(floor_number): count
                for floor_number, count in counts.items()
            }
        if type(floor) is not int or floor not in {1, 2}:
            raise ValueError("El piso de la emergencia debe ser 1 o 2.")
        self.emergency_type = emergency_type
        self.zone = zone
        self.people = people
        self.floor = floor
        self.danger_zones = self._validate_danger_zones(
            danger_zones,
            floor,
        )
        self.fire_zones = self._validate_danger_zones(
            fire_zones,
            floor,
        )
        if self.fire_zones and emergency_type not in {"incendio", "combinada"}:
            raise ValueError(
                "Las zonas con fuego requieren una emergencia de incendio."
            )
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

        allowed = {
            "emergency_type",
            "zone",
            "people",
            "people_by_floor",
            "danger_zones",
            "fire_zones",
            "blocked_exits",
            "floor",
        }
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
        people_by_floor = data.get("people_by_floor")
        danger_zones = data.get("danger_zones")
        fire_zones = data.get("fire_zones")
        blocked_exits = data.get("blocked_exits", [])
        floor = data.get("floor", 1)

        if not isinstance(emergency_type, str) or emergency_type not in EMERGENCY_TYPES:
            raise ValueError(
                "Tipo de emergencia inválido. Use incendio, terremoto, "
                "zona_peligrosa, salida_bloqueada o combinada."
            )
        if not isinstance(zone, str) or _normalize(zone) not in ZONE_CELLS:
            raise ValueError(
                "Zona desconocida. Use un nombre de habitación o 'Pasillo central'."
            )
        if (
            people_by_floor is None
            and (type(people) is not int or not 1 <= people <= MAX_PEOPLE)
        ):
            raise ValueError(
                f"'people' debe ser un entero entre 1 y {MAX_PEOPLE}."
            )
        if type(floor) is not int or floor not in {1, 2}:
            raise ValueError("'floor' debe ser el entero 1 o 2.")
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
            floor=floor,
            people_by_floor=people_by_floor,
            danger_zones=danger_zones,
            fire_zones=fire_zones,
        )

    @staticmethod
    def _validate_danger_zones(danger_zones, default_floor):
        if danger_zones is None:
            return ()
        if not isinstance(danger_zones, list):
            raise ValueError("'danger_zones' debe ser una lista de zonas.")
        normalized_zones = []
        for item in danger_zones:
            if isinstance(item, str):
                zone = item
                floor = default_floor
            elif isinstance(item, dict) and set(item) == {"zone", "floor"}:
                zone = item["zone"]
                floor = item["floor"]
                if type(floor) is not int or floor not in {1, 2}:
                    raise ValueError(
                        "El piso de cada zona peligrosa debe ser 1 o 2."
                    )
            else:
                raise ValueError(
                    "Cada zona peligrosa debe ser un nombre o incluir zona y piso."
                )
            if not isinstance(zone, str) or _normalize(zone) not in ZONE_CELLS:
                raise ValueError(f"Zona peligrosa desconocida: {zone}.")
            canonical = next(
                name
                for name in ZONE_CELLS
                if _normalize(name) == _normalize(zone)
            )
            entry = (canonical, floor)
            if entry not in normalized_zones:
                normalized_zones.append(entry)
        return tuple(normalized_zones)

    @classmethod
    def from_json(cls, content):
        try:
            data = json.loads(content)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("La respuesta recibida no contiene JSON válido.") from error
        return cls.from_dict(data)

    def zone_positions(self):
        return self.positions_for_zone(self.zone)

    def positions_for_zone(self, zone, floor=None):
        x, y, width, height = ZONE_CELLS[_normalize(zone)]
        target_floor = self.floor if floor is None else floor
        if target_floor == 2:
            y += FLOOR_HEIGHT
        return {
            (column, row)
            for row in range(y, y + height)
            for column in range(x, x + width)
        }

    def __str__(self):
        people_description = (
            ", ".join(
                f"piso {floor}: {count}"
                for floor, count in self.people_by_floor.items()
            )
            if self.people_by_floor is not None
            else str(self.people)
        )
        return (
            f"Emergencia: {self.emergency_type}\n"
            f"Zona afectada: {self.zone} (piso {self.floor})\n"
            "Zonas peligrosas: "
            + (
                ", ".join(
                    f"{zone} (piso {floor})"
                    for zone, floor in self.danger_zones
                )
                or "ninguna adicional"
            )
            + "\n"
            f"Personas: {people_description}\n"
            f"Salidas bloqueadas: {', '.join(self.blocked_exits) or 'ninguna'}"
        )
