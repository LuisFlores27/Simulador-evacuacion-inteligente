import random
import math
from concurrent.futures import ThreadPoolExecutor
import pygame

from ai.client import GenerativeAIClient
from emergency.application import apply_scenario
from emergency.scenario import (
    EmergencyScenario,
    EXIT_IDS,
    FLOOR_HEIGHT,
    ZONE_CELLS,
)
from evacuation.grid import Grid
from evacuation.manager import EvacuationManager
from graphics.config import (
    ALTO,
    ANCHO,
    COLS,
    FLOORS,
    FPS,
    PANEL,
    ROWS,
    STAIR_X,
    TILE,
    TOTAL_ROWS,
)
from ui.interfaz import (
    COLORS,
    INSTRUCTION_MAX_HEIGHT,
    INSTRUCTION_MIN_HEIGHT,
    INSTRUCTION_TOP,
    PREVIEW_BACK_BUTTON,
    PREVIEW_BUTTON,
    Interfaz,
)


# ============================================================
# TIPOS DE CELDA
# ============================================================

PARED = 0
PISO = 1
PASILLO = 2
PUERTA = 3
SALIDA = 4
ESCALERA = 5

# ============================================================
# HABITACIONES
# ============================================================

HABITACIONES = [
    (*ZONE_CELLS[key], name)
    for key, name in (
        ("laboratorio", "Laboratorio"),
        ("aula 1", "Aula 1"),
        ("aula 2", "Aula 2"),
        ("oficina", "Oficina"),
        ("biblioteca", "Biblioteca"),
        ("aula 3", "Aula 3"),
        ("aula 4", "Aula 4"),
        ("sala", "Sala"),
    )
]


# ============================================================
# SALIDAS
# ============================================================

SALIDAS = {
    (position[0], position[1] + FLOOR_HEIGHT): identifier.upper()
    for identifier, position in EXIT_IDS.items()
}


# Colores de rutas según la salida
COLOR_SALIDA = {
    "A": (64, 158, 255),
    "B": (255, 177, 74),
    "C": (54, 203, 174),
    "D": (194, 119, 255),
}


# ============================================================
# EDIFICIO
# ============================================================

class Edificio:

    def __init__(self):

        self.mapa = [
            [PARED for _ in range(COLS)]
            for _ in range(TOTAL_ROWS)
        ]

        self.nombres_habitaciones = []
        self.grid = None

        self.fuente = pygame.font.SysFont("arial", 13, bold=True)
        self.fuente_piso = pygame.font.SysFont("arial", 16, bold=True)
        self.fuente_zona = pygame.font.SysFont("arial", 12, bold=True)

        self.construir_edificio()

    def construir_edificio(self):

        # ----------------------------------------------------
        # Habitaciones
        # ----------------------------------------------------

        for piso in (2, 1):
            offset_y = (2 - piso) * FLOOR_HEIGHT

            for x, y, ancho, alto, nombre in HABITACIONES:
                y += offset_y
                self.nombres_habitaciones.append(
                    (x, y, ancho, alto, f"{nombre} (P{piso})")
                )

                for fila in range(y, y + alto):
                    for columna in range(x, x + ancho):
                        if 0 <= fila < TOTAL_ROWS and 0 <= columna < COLS:
                            self.mapa[fila][columna] = PISO

            # Pasillo central
            x, y, width, height = ZONE_CELLS["pasillo central"]
            for fila in range(y + offset_y, y + offset_y + height):
                for columna in range(x, x + width):
                    self.mapa[fila][columna] = PASILLO

            # Puertas
            for x, y, ancho, alto, _ in HABITACIONES:
                fila_puerta = (5 if y < 6 else 11) + offset_y
                puerta_x = x + ancho // 2
                if 0 <= puerta_x < COLS and 0 <= fila_puerta < TOTAL_ROWS:
                    self.mapa[fila_puerta][puerta_x] = PUERTA

        # Close the stairwell sides so rooms cannot enter it through a wall.
        for y in range(11, FLOOR_HEIGHT + 6):
            self.mapa[y][STAIR_X - 1] = PARED
            self.mapa[y][STAIR_X + 1] = PARED

        # La escalera es el único paso que conecta ambos pisos.
        for y in range(11, FLOOR_HEIGHT + 7):
            self.mapa[y][STAIR_X] = ESCALERA

        # ----------------------------------------------------
        # Salidas del primer piso
        # ----------------------------------------------------

        for posicion in SALIDAS:

            x, y = posicion

            self.mapa[y][x] = SALIDA

    @property
    def bloqueadas(self):
        return set(self.grid.blocked_exits) if self.grid else set()

    @property
    def fuego(self):
        if self.grid is None:
            return set()
        return {
            node.position
            for row in self.grid.nodes
            for node in row
            if node.node_type == "incendio"
        }

    @property
    def zonas_peligrosas(self):
        if self.grid is None:
            return set()
        return {
            node.position
            for row in self.grid.nodes
            for node in row
            if node.node_type == "peligro"
        }

    def casilla_a_pixel(self, posicion):

        x, y = posicion

        return (
            x * TILE + TILE // 2,
            y * TILE + TILE // 2
        )

    def dibujar(self, pantalla, tiempo):

        # ----------------------------------------------------
        # Mapa base
        # ----------------------------------------------------

        colores = {
            PARED: COLORS["wall"],
            PISO: COLORS["floor"],
            PASILLO: COLORS["corridor"],
            PUERTA: (232, 177, 91),
            SALIDA: COLORS["green"],
            ESCALERA: (185, 202, 221),
        }

        for y in range(TOTAL_ROWS):
            for x in range(COLS):

                rect = pygame.Rect(
                    x * TILE,
                    y * TILE,
                    TILE,
                    TILE
                )

                color = colores[self.mapa[y][x]]
                if self.mapa[y][x] == PISO and (x + y) % 2:
                    color = COLORS["floor_alt"]
                pygame.draw.rect(pantalla, color, rect)

                if self.mapa[y][x] == PARED:
                    pygame.draw.rect(
                        pantalla,
                        COLORS["wall_line"],
                        rect,
                        1,
                    )
                else:
                    pygame.draw.rect(
                        pantalla,
                        (215, 224, 234),
                        rect,
                        1,
                    )

                if self.mapa[y][x] == PUERTA:
                    pygame.draw.line(
                        pantalla,
                        (150, 99, 40),
                        (x * TILE + 8, y * TILE + TILE - 6),
                        (x * TILE + TILE - 8, y * TILE + TILE - 6),
                        2,
                    )

                if self.mapa[y][x] == ESCALERA:
                    pygame.draw.line(
                        pantalla,
                        (248, 251, 255),
                        (x * TILE + 7, y * TILE + 7),
                        (x * TILE + TILE - 7, y * TILE + 7),
                        2,
                    )
                    pygame.draw.line(
                        pantalla,
                        (113, 137, 165),
                        (x * TILE + 4, y * TILE),
                        (x * TILE + 4, y * TILE + TILE),
                        3,
                    )
                    pygame.draw.line(
                        pantalla,
                        (113, 137, 165),
                        (x * TILE + TILE - 4, y * TILE),
                        (x * TILE + TILE - 4, y * TILE + TILE),
                        3,
                    )

        for piso, indice_visual in ((2, 0), (1, 1)):
            badge = pygame.Rect(
                8,
                indice_visual * FLOOR_HEIGHT * TILE + 5,
                82,
                25,
            )
            pygame.draw.rect(
                pantalla,
                COLORS["background_soft"],
                badge,
                border_radius=8,
            )
            pygame.draw.rect(
                pantalla,
                COLORS["border"],
                badge,
                width=1,
                border_radius=8,
            )
            texto = self.fuente_piso.render(
                f"PISO {piso}",
                True,
                COLORS["text"],
            )
            pantalla.blit(
                texto,
                texto.get_rect(center=badge.center),
            )

        # ----------------------------------------------------
        # FUEGO ANIMADO
        # ----------------------------------------------------

        for x, y in self.zonas_peligrosas:
            px = x * TILE
            py = y * TILE
            tile = pygame.Rect(px + 2, py + 2, TILE - 4, TILE - 4)
            pygame.draw.rect(
                pantalla,
                (255, 226, 166),
                tile,
                border_radius=6,
            )
            pygame.draw.rect(
                pantalla,
                (233, 166, 65),
                tile,
                width=2,
                border_radius=6,
            )
            pygame.draw.circle(
                pantalla,
                (177, 106, 31),
                (px + TILE // 2, py + TILE // 2),
                8,
            )
            texto = self.fuente.render("!", True, (255, 250, 238))
            pantalla.blit(
                texto,
                texto.get_rect(center=(px + TILE // 2, py + TILE // 2)),
            )

        for x, y in self.fuego:

            px = x * TILE
            py = y * TILE

            # El valor cambia continuamente para producir
            # el efecto de parpadeo.
            variacion = math.sin(
                tiempo * 8
                + x * 1.7
                + y * 2.3
            )

            rojo = 238
            verde = int(78 + 30 * variacion)

            color_fuego = (
                rojo,
                verde,
                48
            )

            tile = pygame.Rect(px + 2, py + 2, TILE - 4, TILE - 4)
            pygame.draw.rect(pantalla, color_fuego, tile, border_radius=6)
            pygame.draw.rect(
                pantalla,
                (255, 208, 153),
                tile,
                width=1,
                border_radius=6,
            )

            # Llama interior
            radio = int(
                6 + 2 * math.sin(
                    tiempo * 10
                    + x
                )
            )

            pygame.draw.circle(
                pantalla,
                (255, 205, 101),
                (
                    px + TILE // 2,
                    py + TILE // 2
                ),
                radio
            )

        # ----------------------------------------------------
        # SALIDAS
        # ----------------------------------------------------

        for posicion in SALIDAS:

            x, y = posicion

            px = x * TILE
            py = y * TILE

            bloqueada = (
                posicion in self.bloqueadas
            )

            if bloqueada:

                tile_color = COLORS["red"]
                pygame.draw.rect(
                    pantalla,
                    tile_color,
                    (px + 2, py + 2, TILE - 4, TILE - 4),
                    border_radius=7,
                )
                pygame.draw.rect(
                    pantalla,
                    (255, 213, 214),
                    (px + 2, py + 2, TILE - 4, TILE - 4),
                    width=1,
                    border_radius=7,
                )

                pygame.draw.line(
                    pantalla,
                    (255, 255, 255),
                    (
                        px + 6,
                        py + 6
                    ),
                    (
                        px + TILE - 6,
                        py + TILE - 6
                    ),
                    4
                )

                pygame.draw.line(
                    pantalla,
                    (255, 255, 255),
                    (
                        px + TILE - 6,
                        py + 6
                    ),
                    (
                        px + 6,
                        py + TILE - 6
                    ),
                    4
                )

            else:

                pygame.draw.rect(
                    pantalla,
                    COLORS["green"],
                    (px + 2, py + 2, TILE - 4, TILE - 4),
                    border_radius=7,
                )
                pygame.draw.rect(
                    pantalla,
                    (197, 255, 226),
                    (px + 2, py + 2, TILE - 4, TILE - 4),
                    width=1,
                    border_radius=7,
                )

        # ----------------------------------------------------
        # NOMBRES DE HABITACIONES
        # ----------------------------------------------------

        hazard_positions = self.zonas_peligrosas | self.fuego
        for (
            x,
            y,
            ancho,
            alto,
            nombre
        ) in self.nombres_habitaciones:

            tiene_peligro = any(
                x <= peligro_x < x + ancho
                and y <= peligro_y < y + alto
                for peligro_x, peligro_y in hazard_positions
            )
            color_fondo = (116, 66, 43) if tiene_peligro else (248, 250, 253)
            color_borde = COLORS["amber"] if tiene_peligro else (209, 220, 232)
            color_texto = (255, 239, 211) if tiene_peligro else (74, 91, 112)
            texto = self.fuente_zona.render(
                nombre,
                True,
                color_texto,
            )
            badge = texto.get_rect(topleft=(x * TILE + 6, y * TILE + 4))
            badge.inflate_ip(12, 6)
            pygame.draw.rect(
                pantalla,
                color_fondo,
                badge,
                border_radius=6,
            )
            pygame.draw.rect(
                pantalla,
                color_borde,
                badge,
                width=1,
                border_radius=6,
            )

            pantalla.blit(
                texto,
                texto.get_rect(center=badge.center),
            )

    def dibujar_nombres_salidas(self, pantalla):

        # Se dibujan DESPUÉS de las personas para garantizar
        # que ninguna persona tape la letra de la salida.

        for posicion, letra in SALIDAS.items():

            x, y = posicion

            px = x * TILE
            py = y * TILE

            if posicion in self.bloqueadas:
                color = (255, 255, 255)
            else:
                color = (255, 255, 255, 255)

            texto = self.fuente.render(
                letra,
                True,
                color
            )

            rect = texto.get_rect(
                center=(
                    px + TILE // 2,
                    py + TILE // 2
                )
            )

            pantalla.blit(
                texto,
                rect
            )

    def crear_logical_grid(self):

        grid = Grid(
            width=COLS,
            height=TOTAL_ROWS
        )
        grid.exit_offset_y = FLOOR_HEIGHT
        grid.floor_offsets = {1: FLOOR_HEIGHT, 2: 0}
        grid.stair_route = [
            (STAIR_X, y)
            for y in range(10, FLOOR_HEIGHT + 7)
        ]
        grid.stair_exit_landing = (
            STAIR_X + 1,
            FLOOR_HEIGHT + 6,
        )

        # ----------------------------------------------------
        # Mapa visual → mapa lógico
        # ----------------------------------------------------

        for y in range(TOTAL_ROWS):
            for x in range(COLS):

                tipo = self.mapa[y][x]

                if tipo == PARED:

                    grid.set_obstacle(
                        x,
                        y
                    )

                elif tipo == SALIDA:

                    grid.register_exit(
                        (x, y),
                        SALIDAS[(x, y)]
                    )

                else:

                    grid.set_node_type(
                        x,
                        y,
                        "libre"
                    )

        return grid


# ============================================================
# PERSONA VISUAL
# ============================================================

class PersonaVisual:

    def __init__(
        self,
        persona,
        edificio,
        tiempo_inicio
    ):

        self.persona = persona
        self.edificio = edificio

        self.x, self.y = (
            edificio.casilla_a_pixel(
                persona.position
            )
        )

        self.destino = None

        self.velocidad = 75

        self.reaccion = random.uniform(
            0,
            3
        )

        self.tiempo_inicio = (
            tiempo_inicio
        )

        # Fase para animar las piernas
        self.fase = random.random() * math.tau

        self.tiempo_evacuacion = None

        # Color según salida
        salida = persona.target_exit

        letra = (
            SALIDAS.get(salida)
            if salida is not None
            else None
        )

        self.color = COLOR_SALIDA.get(letra, (151, 168, 190))

    @property
    def moviendo(self):

        return self.destino is not None

    def actualizar(
        self,
        dt,
        tiempo_actual
    ):

        if self.persona.evacuated:
            return

        # ----------------------------------------------------
        # Tiempo de reacción
        # ----------------------------------------------------

        if (
            tiempo_actual
            - self.tiempo_inicio
            < self.reaccion
        ):
            return

        # ----------------------------------------------------
        # Sin ruta
        # ----------------------------------------------------

        if not self.persona.route:
            return

        # ----------------------------------------------------
        # Siguiente posición
        # ----------------------------------------------------

        siguiente_indice = (
            self.persona.route_index + 1
        )

        if (
            siguiente_indice
            >= len(self.persona.route)
        ):

            if (
                self.persona.position
                == self.persona.target_exit
            ):

                self.persona.evacuate()

                if self.tiempo_evacuacion is None:

                    self.tiempo_evacuacion = (
                        tiempo_actual
                    )

            return

        siguiente = self.persona.route[
            siguiente_indice
        ]

        destino_x, destino_y = (
            self.edificio.casilla_a_pixel(
                siguiente
            )
        )

        if self.destino is None:

            self.destino = (
                destino_x,
                destino_y
            )

        dx = self.destino[0] - self.x
        dy = self.destino[1] - self.y

        distancia = math.hypot(
            dx,
            dy
        )

        desplazamiento = (
            self.velocidad * dt
        )

        if distancia <= desplazamiento:

            self.x = self.destino[0]
            self.y = self.destino[1]

            self.persona.move_next()

            self.destino = None

            if self.persona.evacuated:

                if (
                    self.tiempo_evacuacion
                    is None
                ):

                    self.tiempo_evacuacion = (
                        tiempo_actual
                    )

        else:

            self.x += (
                dx / distancia
            ) * desplazamiento

            self.y += (
                dy / distancia
            ) * desplazamiento

            # Animación de caminar
            self.fase += dt * 14

    def puntos_ruta(self):

        if not self.persona.route:
            return []

        puntos = []

        inicio = (
            self.persona.route_index
        )

        for posicion in (
            self.persona.route[inicio:]
        ):

            puntos.append(
                self.edificio.casilla_a_pixel(
                    posicion
                )
            )

        return puntos

    def dibujar(self, pantalla):

        # ----------------------------------------------------
        # No dibujar a la persona una vez evacuada
        # ----------------------------------------------------

        if self.persona.evacuated:
            return

        # ----------------------------------------------------
        # Posición
        # ----------------------------------------------------

        centro_x = int(self.x)
        centro_y = int(self.y)

        # ----------------------------------------------------
        # Animación de piernas
        # ----------------------------------------------------

        if self.moviendo:

            movimiento_piernas = (
                math.sin(self.fase) * 5
            )

            elevacion = (
                abs(
                    math.sin(self.fase)
                ) * 2
            )

        else:

            movimiento_piernas = 0
            elevacion = 0

        # ----------------------------------------------------
        # Sombra
        pygame.draw.ellipse(
            pantalla,
            (177, 190, 204),
            (centro_x - 8, centro_y + 12, 16, 5),
        )

        # Pierna izquierda
        # ----------------------------------------------------

        pygame.draw.line(
            pantalla,
            (49, 62, 79),
            (
                centro_x - 3,
                centro_y + 6 - elevacion
            ),
            (
                centro_x - 3
                + movimiento_piernas,
                centro_y + 16
            ),
            3
        )

        # ----------------------------------------------------
        # Pierna derecha
        # ----------------------------------------------------

        pygame.draw.line(
            pantalla,
            (49, 62, 79),
            (
                centro_x + 3,
                centro_y + 6 - elevacion
            ),
            (
                centro_x + 3
                - movimiento_piernas,
                centro_y + 16
            ),
            3
        )

        # ----------------------------------------------------
        # Cuerpo
        # ----------------------------------------------------

        body_rect = pygame.Rect(
            centro_x - 6,
            centro_y - 9 - int(elevacion),
            12,
            15,
        )
        pygame.draw.rect(
            pantalla,
            (255, 255, 255),
            body_rect.move(1, 2),
            border_radius=5,
        )
        pygame.draw.rect(
            pantalla,
            self.color,
            body_rect,
            border_radius=5,
        )
        pygame.draw.line(
            pantalla,
            tuple(max(0, channel - 35) for channel in self.color),
            (centro_x, body_rect.top + 3),
            (centro_x, body_rect.bottom - 3),
            1,
        )

        # ----------------------------------------------------
        # Cabeza
        # ----------------------------------------------------

        pygame.draw.circle(
            pantalla,
            (255, 220, 187),
            (
                centro_x,
                centro_y - 14 - int(elevacion)
            ),
            6
        )
        pygame.draw.circle(
            pantalla,
            (255, 247, 235),
            (centro_x - 2, centro_y - 16 - int(elevacion)),
            2,
        )


# ============================================================
# SIMULACIÓN
# ============================================================

class Simulacion(Interfaz):

    def __init__(self):
        self.ai_client = GenerativeAIClient()
        self.ai_executor = ThreadPoolExecutor(max_workers=1)
        self.mapa_pantalla = pygame.Surface((ANCHO, TOTAL_ROWS * TILE))
        self.ai_future = None
        self.error_ia = None
        self.input_mode = False
        self.instruccion = ""
        self.cursor_instruccion = 0
        self.selection_anchor = None
        self.preview_mode = False
        self.estado_ia = (
            "IA disponible"
            if self.ai_client.is_configured
            else "IA sin configurar; usa T para escribir o 1-4 para escenarios locales"
        )
        self.fuente = pygame.font.SysFont(
            "arial",
            16,
            bold=True
        )
        self.preparar_simulacion()
        self.inicio_pendiente = True
        self.input_mode = True
        self.estado_ia = (
            "Describe la emergencia y especifica el piso; pulsa Enter."
        )
        pygame.key.start_text_input()

    def preparar_simulacion(self):
        self.edificio = Edificio()
        self.edificio_previsualizacion = Edificio()
        self.instruccion = ""
        self.aplicar_escenario(
            EmergencyScenario(
                "combinada",
                "Sala",
                people=24,
                blocked_exits=["B", "C"],
            )
        )

    def _posiciones_iniciales(self, cantidad, grid, floor=1):
        disponibles = []
        offset_y = (2 - floor) * FLOOR_HEIGHT
        for x, y, ancho, alto, _ in HABITACIONES:
            for fila in range(y + offset_y, y + offset_y + alto):
                for columna in range(x, x + ancho):
                    node = grid.get_node(columna, fila)
                    if (
                        node is not None
                        and node.walkable
                        and self.edificio.mapa[fila][columna] == PISO
                    ):
                        disponibles.append(node.position)
        if cantidad > len(disponibles):
            return []
        return random.sample(disponibles, cantidad)

    def aplicar_escenario(self, scenario):
        if self.ai_future is not None:
            self.ai_future.cancel()
            self.ai_future = None
        if self.input_mode:
            pygame.key.stop_text_input()
        self.input_mode = False
        nuevo_grid = self.edificio.crear_logical_grid()
        people = apply_scenario(
            nuevo_grid,
            scenario,
            lambda count, grid: self._posiciones_escenario(scenario, count, grid),
        )
        manager = EvacuationManager(nuevo_grid, people)
        manager.calculate_routes()

        self.grid = nuevo_grid
        self.edificio.grid = nuevo_grid
        self.people = people
        self.people_per_floor = {
            1: sum(person.position[1] >= FLOOR_HEIGHT for person in people),
            2: sum(person.position[1] < FLOOR_HEIGHT for person in people),
        }
        self.manager = manager
        self.personas_visuales = [
            PersonaVisual(persona, self.edificio, 0)
            for persona in people
        ]
        self.escenario = scenario
        self.error_ia = None
        self.tiempo = 0.0
        self.terminada = False
        self.tiempo_final = None
        self.inicio_pendiente = False
        self.instruccion = ""
        self.cursor_instruccion = 0
        self.estado_ia = (
            f"Escenario aplicado: {scenario.emergency_type} en {scenario.zone}, "
            f"piso {scenario.floor}."
        )

    def _posiciones_escenario(self, scenario, cantidad, grid):
        if scenario.people_by_floor is None:
            return self._posiciones_iniciales(cantidad, grid, scenario.floor)
        positions = []
        for floor, floor_count in scenario.people_by_floor.items():
            positions.extend(
                self._posiciones_iniciales(floor_count, grid, floor)
            )
        return positions

    def volver_a_inicio(self):
        if self.ai_future is not None:
            self.ai_future.cancel()
            self.ai_future = None
        self.input_mode = True
        self.inicio_pendiente = True
        self.instruccion = ""
        self.cursor_instruccion = 0
        self.estado_ia = "Describe la emergencia y especifica el piso; pulsa Enter."
        self.error_ia = None
        pygame.key.start_text_input()

    def reiniciar_simulacion(self):
        if self.terminada:
            self.aplicar_escenario(self.escenario)









    def enviar_instruccion(self):
        if self.ai_future is not None:
            self.estado_ia = "Espera a que termine la solicitud actual."
            return
        try:
            self.ai_client.validate_instruction(self.instruccion)
        except ValueError as error:
            self.estado_ia = str(error)
            self.error_ia = str(error)
            return
        instruction = self.instruccion.strip()
        self.instruccion = instruction
        self.cursor_instruccion = len(instruction)
        self.ai_future = self.ai_executor.submit(
            self.ai_client.generate_scenario,
            instruction,
        )
        self.error_ia = None
        self.input_mode = False
        pygame.key.stop_text_input()
        self.estado_ia = "Consultando la API de IA..."

    def actualizar(self, dt):

        if self.ai_future is not None and self.ai_future.done():
            future = self.ai_future
            self.ai_future = None
            try:
                scenario_data = future.result()
                scenario = EmergencyScenario.from_dict(scenario_data)
                self.aplicar_escenario(scenario)
                self.instruccion = ""
            except (ValueError, RuntimeError) as error:
                self.estado_ia = str(error)
                self.error_ia = str(error)
                if self.inicio_pendiente:
                    self.input_mode = True
                    pygame.key.start_text_input()

        if self.inicio_pendiente:
            return

        if self.terminada:
            return

        self.tiempo += dt
        self.manager.elapsed_time = self.tiempo

        for persona_visual in (
            self.personas_visuales
        ):

            persona_visual.actualizar(
                dt,
                self.tiempo
            )

        # ----------------------------------------------------
        if self.manager.is_finished():
            self.terminada = True
            self.tiempo_final = self.tiempo

    def desplazamiento_terremoto(self):
        if self.escenario.emergency_type != "terremoto" or self.terminada:
            return (0, 0)
        return (
            round(
                math.sin(self.tiempo * 37) * 5
                + math.sin(self.tiempo * 61) * 2
            ),
            round(
                math.cos(self.tiempo * 43) * 4
                + math.sin(self.tiempo * 67) * 2
            ),
        )

    def dibujar(self, pantalla):
        if self.preview_mode:
            self.dibujar_previsualizacion(pantalla)
            return
        if self.inicio_pendiente:
            self.dibujar_inicio(pantalla)
            return

        # ----------------------------------------------------
        # Fondo
        # ----------------------------------------------------

        pantalla.fill(COLORS["background"])
        mapa_pantalla = self.mapa_pantalla
        mapa_pantalla.fill(COLORS["background"])

        # ----------------------------------------------------
        # Edificio
        # ----------------------------------------------------

        self.edificio.dibujar(
            mapa_pantalla,
            self.tiempo
        )

        # ----------------------------------------------------
        # Rutas
        # ----------------------------------------------------

        for persona_visual in (
            self.personas_visuales
        ):

            if persona_visual.persona.evacuated:
                continue

            puntos = (
                persona_visual.puntos_ruta()
            )

            if len(puntos) > 1:

                pygame.draw.lines(
                    mapa_pantalla,
                    (255, 255, 255),
                    False,
                    puntos,
                    5,
                )
                pygame.draw.lines(
                    mapa_pantalla,
                    persona_visual.color,
                    False,
                    puntos,
                    2,
                )

        # ----------------------------------------------------
        # Personas
        # ----------------------------------------------------

        for persona_visual in (
            self.personas_visuales
        ):

            persona_visual.dibujar(
                mapa_pantalla
            )

        # ----------------------------------------------------
        # Dibujar letras de salidas
        # ENCIMA de las personas
        # ----------------------------------------------------

        self.edificio.dibujar_nombres_salidas(
            mapa_pantalla
        )

        desplazamiento = self.desplazamiento_terremoto()
        pantalla.blit(mapa_pantalla, desplazamiento)

        # ----------------------------------------------------
        # Panel
        # ----------------------------------------------------

        self.dibujar_panel(
            pantalla
        )
