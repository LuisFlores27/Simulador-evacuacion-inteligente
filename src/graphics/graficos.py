import random
import math
from concurrent.futures import ThreadPoolExecutor
import pygame

from ai.client import GenerativeAIClient
from emergency.application import apply_scenario
from emergency.scenario import EmergencyScenario, EXIT_IDS, ZONE_CELLS
from evacuation.grid import Grid
from evacuation.manager import EvacuationManager


# ============================================================
# CONFIGURACIÓN VISUAL
# ============================================================

TILE = 32

COLS = 30
ROWS = 18

PANEL = 88

ANCHO = COLS * TILE
ALTO = ROWS * TILE + PANEL

FPS = 60


# ============================================================
# TIPOS DE CELDA
# ============================================================

PARED = 0
PISO = 1
PASILLO = 2
PUERTA = 3
SALIDA = 4

CAMINABLES = {
    PISO,
    PASILLO,
    PUERTA,
    SALIDA
}


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
    position: identifier.upper()
    for identifier, position in EXIT_IDS.items()
}


# Colores de rutas según la salida
COLOR_SALIDA = {
    "A": (30, 120, 230),
    "B": (120, 120, 120),
    "C": (120, 120, 120),
    "D": (170, 60, 200)
}


# ============================================================
# EDIFICIO
# ============================================================

class Edificio:

    def __init__(self):

        self.mapa = [
            [PARED for _ in range(COLS)]
            for _ in range(ROWS)
        ]

        self.nombres_habitaciones = []
        self.grid = None

        self.fuente = pygame.font.SysFont(
            "arial",
            14,
            bold=True
        )

        self.construir_edificio()

    def construir_edificio(self):

        # ----------------------------------------------------
        # Habitaciones
        # ----------------------------------------------------

        for x, y, ancho, alto, nombre in HABITACIONES:

            self.nombres_habitaciones.append(
                (x, y, ancho, alto, nombre)
            )

            for fila in range(y, y + alto):
                for columna in range(x, x + ancho):

                    if (
                        0 <= fila < ROWS
                        and 0 <= columna < COLS
                    ):
                        self.mapa[fila][columna] = PISO

        # ----------------------------------------------------
        # Pasillo central
        # ----------------------------------------------------

        x, y, width, height = ZONE_CELLS["pasillo central"]
        for fila in range(y, y + height):
            for columna in range(x, x + width):
                self.mapa[fila][columna] = PASILLO

        # ----------------------------------------------------
        # Puertas
        # ----------------------------------------------------

        for x, y, ancho, alto, nombre in HABITACIONES:

            fila_puerta = 5 if y < 6 else 11

            puerta_x = x + ancho // 2

            if (
                0 <= puerta_x < COLS
                and 0 <= fila_puerta < ROWS
            ):
                self.mapa[fila_puerta][puerta_x] = PUERTA

        # ----------------------------------------------------
        # Salidas
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

    def es_caminable(self, x, y):

        if not (
            0 <= x < COLS
            and 0 <= y < ROWS
        ):
            return False

        if self.mapa[y][x] not in CAMINABLES:
            return False
        node = self.grid.get_node(x, y) if self.grid else None
        return node is None or node.walkable

    def salidas_abiertas(self):

        return [
            salida
            for salida in SALIDAS
            if salida not in self.bloqueadas
        ]

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
            PARED: (60, 60, 70),
            PISO: (225, 225, 215),
            PASILLO: (190, 195, 205),
            PUERTA: (150, 100, 50),
            SALIDA: (60, 180, 90)
        }

        for y in range(ROWS):
            for x in range(COLS):

                rect = pygame.Rect(
                    x * TILE,
                    y * TILE,
                    TILE,
                    TILE
                )

                pygame.draw.rect(
                    pantalla,
                    colores[self.mapa[y][x]],
                    rect
                )

                if self.mapa[y][x] != PARED:

                    pygame.draw.rect(
                        pantalla,
                        (170, 170, 175),
                        rect,
                        1
                    )

        # ----------------------------------------------------
        # FUEGO ANIMADO
        # ----------------------------------------------------

        for x, y in self.zonas_peligrosas:
            px = x * TILE
            py = y * TILE
            pygame.draw.rect(
                pantalla,
                (215, 165, 45),
                (px, py, TILE, TILE)
            )
            texto = self.fuente.render("!", True, (45, 35, 20))
            pantalla.blit(texto, texto.get_rect(center=(px + TILE // 2, py + TILE // 2)))

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

            rojo = 235
            verde = int(
                110 + 50 * variacion
            )

            color_fuego = (
                rojo,
                verde,
                20
            )

            pygame.draw.rect(
                pantalla,
                color_fuego,
                (
                    px,
                    py,
                    TILE,
                    TILE
                )
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
                (255, 180, 30),
                (
                    px + TILE // 2,
                    py + TILE // 2
                ),
                radio
            )

        # ----------------------------------------------------
        # SALIDAS
        # ----------------------------------------------------

        for posicion, letra in SALIDAS.items():

            x, y = posicion

            px = x * TILE
            py = y * TILE

            bloqueada = (
                posicion in self.bloqueadas
            )

            if bloqueada:

                pygame.draw.rect(
                    pantalla,
                    (200, 40, 40),
                    (
                        px,
                        py,
                        TILE,
                        TILE
                    )
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
                    (60, 180, 90),
                    (
                        px,
                        py,
                        TILE,
                        TILE
                    )
                )

        # ----------------------------------------------------
        # NOMBRES DE HABITACIONES
        # ----------------------------------------------------

        for (
            x,
            y,
            ancho,
            alto,
            nombre
        ) in self.nombres_habitaciones:

            texto = self.fuente.render(
                nombre,
                True,
                (80, 80, 90)
            )

            pantalla.blit(
                texto,
                (
                    x * TILE + 6,
                    y * TILE + 4
                )
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
            height=ROWS
        )

        # ----------------------------------------------------
        # Mapa visual → mapa lógico
        # ----------------------------------------------------

        for y in range(ROWS):
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

        self.color = (
            COLOR_SALIDA.get(
                letra,
                (90, 90, 90)
            )
        )

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
        # Ruta
        # ----------------------------------------------------

        puntos = self.puntos_ruta()

        if len(puntos) >= 2:

            pygame.draw.lines(
                pantalla,
                self.color,
                False,
                puntos,
                2
            )

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
        # Pierna izquierda
        # ----------------------------------------------------

        pygame.draw.line(
            pantalla,
            (40, 40, 50),
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
            (40, 40, 50),
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

        pygame.draw.rect(
            pantalla,
            self.color,
            (
                centro_x - 5,
                centro_y - 8 - int(elevacion),
                10,
                13
            ),
            border_radius=3
        )

        # ----------------------------------------------------
        # Cabeza
        # ----------------------------------------------------

        pygame.draw.circle(
            pantalla,
            (240, 205, 170),
            (
                centro_x,
                centro_y - 14 - int(elevacion)
            ),
            6
        )


# ============================================================
# SIMULACIÓN
# ============================================================

class Simulacion:

    def __init__(self):
        self.ai_client = GenerativeAIClient()
        self.ai_executor = ThreadPoolExecutor(max_workers=1)
        self.ai_future = None
        self.input_mode = False
        self.instruccion = ""
        self.estado_ia = (
            "IA disponible"
            if self.ai_client.is_configured
            else "IA sin configurar; usa T para escribir o 1-4 para escenarios locales"
        )
        self.fuente = pygame.font.SysFont(
            "arial",
            14,
            bold=True
        )
        self.preparar_simulacion()
        self.inicio_pendiente = True
        self.input_mode = True
        self.estado_ia = (
            "Escribe una emergencia y pulsa Enter; F1-F4 carga escenarios locales."
        )
        pygame.key.start_text_input()

    def preparar_simulacion(self):
        self.edificio = Edificio()
        self.instruccion = ""
        self.aplicar_escenario(
            EmergencyScenario(
                "combinada",
                "Sala",
                people=24,
                blocked_exits=["B", "C"],
            )
        )

    def _posiciones_iniciales(self, cantidad, grid):
        disponibles = []
        for x, y, ancho, alto, _ in HABITACIONES:
            for fila in range(y, y + alto):
                for columna in range(x, x + ancho):
                    node = grid.get_node(columna, fila)
                    if node is not None and node.walkable:
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
            self._posiciones_iniciales
        )
        manager = EvacuationManager(nuevo_grid, people)
        manager.calculate_routes()

        self.grid = nuevo_grid
        self.edificio.grid = nuevo_grid
        self.people = people
        self.manager = manager
        self.personas_visuales = [
            PersonaVisual(persona, self.edificio, 0)
            for persona in people
        ]
        self.escenario = scenario
        self.tiempo = 0.0
        self.terminada = False
        self.tiempo_final = None
        self.inicio_pendiente = False
        self.instruccion = ""
        self.estado_ia = f"Escenario aplicado: {scenario.emergency_type} en {scenario.zone}."

    def volver_a_inicio(self):
        if self.ai_future is not None:
            self.ai_future.cancel()
            self.ai_future = None
        self.input_mode = True
        self.inicio_pendiente = True
        self.instruccion = ""
        self.estado_ia = "Escribe una emergencia y pulsa Enter; F1-F4 carga escenarios locales."
        pygame.key.start_text_input()

    def manejar_evento(self, evento):
        if evento.type == pygame.TEXTINPUT and self.input_mode:
            if len(self.instruccion) < 180:
                self.instruccion += evento.text
            return

        if evento.type != pygame.KEYDOWN:
            return

        escenarios_locales = {
            pygame.K_1: EmergencyScenario("incendio", "Laboratorio", 24),
            pygame.K_KP1: EmergencyScenario("incendio", "Laboratorio", 24),
            pygame.K_2: EmergencyScenario("zona_peligrosa", "Aula 2", 24),
            pygame.K_KP2: EmergencyScenario("zona_peligrosa", "Aula 2", 24),
            pygame.K_3: EmergencyScenario(
                "salida_bloqueada",
                "Pasillo central",
                24,
                blocked_exits=["B", "C"],
            ),
            pygame.K_KP3: EmergencyScenario(
                "salida_bloqueada",
                "Pasillo central",
                24,
                blocked_exits=["B", "C"],
            ),
            pygame.K_4: EmergencyScenario(
                "combinada",
                "Biblioteca",
                24,
                blocked_exits=["A", "D"],
            ),
            pygame.K_KP4: EmergencyScenario(
                "combinada",
                "Biblioteca",
                24,
                blocked_exits=["A", "D"],
            ),
        }

        escenarios_inicio = {
            pygame.K_F1: escenarios_locales[pygame.K_1],
            pygame.K_F2: escenarios_locales[pygame.K_2],
            pygame.K_F3: escenarios_locales[pygame.K_3],
            pygame.K_F4: escenarios_locales[pygame.K_4],
        }

        if self.input_mode:
            if evento.key in escenarios_inicio:
                self.aplicar_escenario(escenarios_inicio[evento.key])
            elif evento.key == pygame.K_ESCAPE:
                if self.inicio_pendiente:
                    self.estado_ia = "Escribe una emergencia o elige un escenario local con F1-F4."
                else:
                    self.input_mode = False
                    self.instruccion = ""
                    pygame.key.stop_text_input()
                    self.estado_ia = "Entrada cancelada. Usa 1-4 para escenarios locales."
            elif evento.key == pygame.K_BACKSPACE:
                self.instruccion = self.instruccion[:-1]
            elif evento.key == pygame.K_RETURN:
                self.enviar_instruccion()
            return

        if evento.key == pygame.K_b:
            self.volver_a_inicio()
            return

        if evento.key in escenarios_locales:
            self.aplicar_escenario(escenarios_locales[evento.key])
        elif evento.key in escenarios_inicio:
            self.aplicar_escenario(escenarios_inicio[evento.key])

    def enviar_instruccion(self):
        if self.ai_future is not None:
            self.estado_ia = "Espera a que termine la solicitud actual."
            return
        if not self.instruccion.strip():
            self.estado_ia = "Escribe una instrucción antes de enviarla."
            return
        instruction = self.instruccion.strip()
        self.ai_future = self.ai_executor.submit(
            self.ai_client.generate_scenario,
            instruction,
        )
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

    def dibujar(self, pantalla):
        if self.inicio_pendiente:
            self.dibujar_inicio(pantalla)
            return

        # ----------------------------------------------------
        # Fondo
        # ----------------------------------------------------

        pantalla.fill(
            (20, 20, 25)
        )

        # ----------------------------------------------------
        # Edificio
        # ----------------------------------------------------

        self.edificio.dibujar(
            pantalla,
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
                    pantalla,
                    persona_visual.color,
                    False,
                    puntos,
                    2
                )

        # ----------------------------------------------------
        # Personas
        # ----------------------------------------------------

        for persona_visual in (
            self.personas_visuales
        ):

            persona_visual.dibujar(
                pantalla
            )

        # ----------------------------------------------------
        # Dibujar letras de salidas
        # ENCIMA de las personas
        # ----------------------------------------------------

        self.edificio.dibujar_nombres_salidas(
            pantalla
        )

        # ----------------------------------------------------
        # Panel
        # ----------------------------------------------------

        self.dibujar_panel(
            pantalla
        )

    def dibujar_inicio(self, pantalla):
        pantalla.fill((20, 20, 25))
        titulo = pygame.font.SysFont("arial", 30, bold=True)
        texto = pygame.font.SysFont("arial", 18)
        lineas = [
            ("SIMULADOR DE EVACUACIÓN", (255, 255, 255), titulo),
            ("Describe el escenario de emergencia y pulsa Enter:", (220, 220, 225), texto),
            (self.instruccion + ("|" if self.input_mode else ""), (120, 210, 255), texto),
            ("Ejemplo: Incendio en el Laboratorio, bloquea la salida norte, 20 personas.", (190, 195, 205), texto),
            ("Escenarios locales sin API: F1 incendio | F2 zona peligrosa | F3 bloqueos | F4 combinada", (190, 195, 205), texto),
            (self.estado_ia, (255, 190, 110), texto),
        ]

        for index, (line, color, font) in enumerate(lineas):
            while font.size(line)[0] > ANCHO - 48 and line:
                line = line[:-2] + "…"
            surface = font.render(line, True, color)
            pantalla.blit(surface, (24, 80 + index * 54))

    def dibujar_panel(self, pantalla):

        y0 = ROWS * TILE

        pygame.draw.rect(
            pantalla,
            (28, 30, 38),
            (
                0,
                y0,
                ANCHO,
                PANEL
            )
        )

        # ----------------------------------------------------
        # Datos
        # ----------------------------------------------------

        resumen = self.manager.get_evacuation_summary()
        usage = resumen.exit_usage
        open_exits = ", ".join(
            self.grid.get_exit_identifier(position)
            for position in self.grid.get_exits()
        ) or "ninguna"
        blocked_exits = ", ".join(
            self.grid.get_exit_identifier(position)
            for position in sorted(self.grid.blocked_exits)
        ) or "ninguna"

        if self.terminada:
            estado = (
                "EVACUACIÓN COMPLETA"
                if resumen.complete
                else "SIMULACIÓN FINALIZADA: quedaron personas sin evacuar"
            )
            result_line = (
                f"{estado} en {self.tiempo_final:.1f} s | "
                f"Uso real de salidas: "
                f"A {usage.get(EXIT_IDS['a'], 0)}  "
                f"B {usage.get(EXIT_IDS['b'], 0)}  "
                f"C {usage.get(EXIT_IDS['c'], 0)}  "
                f"D {usage.get(EXIT_IDS['d'], 0)} | B: nuevo escenario"
            )
            result_color = (100, 230, 120) if resumen.complete else (255, 170, 90)
        else:
            result_line = (
                f"En curso | Sin ruta: {resumen.people_without_route} | "
                f"Personas pendientes: {resumen.people_not_evacuated} | "
                f"B: nuevo escenario"
            )
            result_color = (230, 230, 235)

        lines = [
            (
                f"Evacuados: {resumen.people_evacuated}/{resumen.total_people}  "
                f"Tiempo: {self.tiempo:.1f} s"
            ),
            (
                f"Salidas disponibles ({resumen.available_exits}): {open_exits}  |  "
                f"Bloqueadas ({resumen.blocked_exits}): {blocked_exits}"
            ),
            result_line,
        ]
        colors = [
            (255, 255, 255),
            (255, 255, 255),
            result_color,
        ]

        for index, (line, color) in enumerate(zip(lines, colors)):
            while self.fuente.size(line)[0] > ANCHO - 24 and line:
                line = line[:-2] + "…"
            text = self.fuente.render(line, True, color)
            pantalla.blit(text, (12, y0 + 4 + index * 25))
