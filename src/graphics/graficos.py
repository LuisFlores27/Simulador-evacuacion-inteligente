import random
import math
import pygame

from evacuation.grid import Grid
from evacuation.manager import EvacuationManager
from evacuation.person import create_people


# ============================================================
# CONFIGURACIÓN VISUAL
# ============================================================

TILE = 32

COLS = 30
ROWS = 18

PANEL = 64

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
    (1, 1, 6, 4, "Laboratorio"),
    (8, 1, 7, 4, "Aula 1"),
    (16, 1, 7, 4, "Aula 2"),
    (24, 1, 5, 4, "Oficina"),

    (1, 12, 6, 5, "Biblioteca"),
    (8, 12, 7, 5, "Aula 3"),
    (16, 12, 7, 5, "Aula 4"),
    (24, 12, 5, 5, "Sala"),
]


# ============================================================
# SALIDAS
# ============================================================

SALIDAS = {
    (0, 8): "A",
    (29, 8): "B",
    (15, 5): "C",
    (15, 11): "D"
}


# ============================================================
# ESCENARIO VISUAL
# ============================================================

SALIDAS_BLOQUEADAS = {
    (29, 8),
    (15, 5)
}


ZONA_FUEGO = {
    (c, f)
    for c in range(26, 29)
    for f in range(7, 10)
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

        for y in range(6, 11):
            for x in range(1, COLS - 1):
                self.mapa[y][x] = PASILLO

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

        # ----------------------------------------------------
        # Salidas bloqueadas
        # ----------------------------------------------------

        self.bloqueadas = set(
            SALIDAS_BLOQUEADAS
        )

        # ----------------------------------------------------
        # Zona de fuego
        # ----------------------------------------------------

        self.fuego = set(
            ZONA_FUEGO
        )

    def es_caminable(self, x, y):

        if not (
            0 <= x < COLS
            and 0 <= y < ROWS
        ):
            return False

        if (x, y) in self.bloqueadas:
            return False

        if (x, y) in self.fuego:
            return False

        return self.mapa[y][x] in CAMINABLES

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

                    grid.set_exit(
                        x,
                        y
                    )

                else:

                    grid.set_node_type(
                        x,
                        y,
                        "libre"
                    )

        # ----------------------------------------------------
        # Zonas peligrosas
        # ----------------------------------------------------

        for x, y in self.fuego:

            if (
                0 <= x < COLS
                and 0 <= y < ROWS
            ):

                if (
                    x,
                    y
                ) not in self.bloqueadas:

                    grid.set_danger(
                        x,
                        y
                    )

        # ----------------------------------------------------
        # Bloquear salidas
        # ----------------------------------------------------

        for posicion in self.bloqueadas:

            grid.block_exit(
                posicion
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

        self.reiniciar()

    def reiniciar(self):

        # ----------------------------------------------------
        # Edificio
        # ----------------------------------------------------

        self.edificio = Edificio()

        # ----------------------------------------------------
        # Grid lógico
        # ----------------------------------------------------

        self.grid = (
            self.edificio.crear_logical_grid()
        )

        # ----------------------------------------------------
        # Personas
        # ----------------------------------------------------

        posiciones = []

        for (
            x,
            y,
            ancho,
            alto,
            nombre
        ) in HABITACIONES:

            posiciones_habitacion = []

            for fila in range(
                y,
                y + alto
            ):

                for columna in range(
                    x,
                    x + ancho
                ):

                    if self.edificio.es_caminable(
                        columna,
                        fila
                    ):

                        posiciones_habitacion.append(
                            (
                                columna,
                                fila
                            )
                        )

            cantidad = min(
                3,
                len(posiciones_habitacion)
            )

            if cantidad > 0:

                seleccionadas = random.sample(
                    posiciones_habitacion,
                    cantidad
                )

                posiciones.extend(
                    seleccionadas
                )

        # ----------------------------------------------------
        # Personas lógicas
        # ----------------------------------------------------

        self.people = create_people(
            posiciones
        )

        # ----------------------------------------------------
        # Gestor de evacuación
        # ----------------------------------------------------

        self.manager = EvacuationManager(
            self.grid,
            self.people
        )

        # ----------------------------------------------------
        # Calcular rutas
        # ----------------------------------------------------

        self.manager.calculate_routes()

        # ----------------------------------------------------
        # Personas visuales
        # ----------------------------------------------------

        self.personas_visuales = []

        for persona in self.people:

            self.personas_visuales.append(
                PersonaVisual(
                    persona,
                    self.edificio,
                    0
                )
            )

        # ----------------------------------------------------
        # Tiempo
        # ----------------------------------------------------

        self.tiempo = 0

        self.terminada = False

        self.tiempo_final = None

        # ----------------------------------------------------
        # Panel
        # ----------------------------------------------------

        self.fuente = pygame.font.SysFont(
            "arial",
            14,
            bold=True
        )

    def actualizar(self, dt):

        if self.terminada:
            return

        self.tiempo += dt

        for persona_visual in (
            self.personas_visuales
        ):

            persona_visual.actualizar(
                dt,
                self.tiempo
            )

        # ----------------------------------------------------
        # Comprobar evacuación completa
        # ----------------------------------------------------

        if self.manager.all_evacuated():

            self.terminada = True

            self.tiempo_final = (
                self.tiempo
            )

    def dibujar(self, pantalla):

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

        resumen = (
            self.manager
            .get_evacuation_summary()
        )

        evacuadas = (
            resumen["people_evacuated"]
        )

        total = (
            resumen["total_people"]
        )

        sin_ruta = (
            resumen["people_without_route"]
        )

        uso_salidas = (
            resumen["exit_usage"]
        )

        abiertas = ", ".join(
            SALIDAS[posicion]
            for posicion
            in self.edificio.salidas_abiertas()
        )

        bloqueadas = ", ".join(
            SALIDAS[posicion]
            for posicion
            in sorted(
                self.edificio.bloqueadas
            )
        )

        # ----------------------------------------------------
        # Primera línea
        # ----------------------------------------------------

        linea1 = (
            f"Evacuados: "
            f"{evacuadas}/{total}"
            f"    "
            f"Tiempo: "
            f"{self.tiempo:4.1f} s"
            f"    "
            f"Abiertas: {abiertas}"
            f"    "
            f"Bloqueadas: {bloqueadas}"
        )

        texto1 = self.fuente.render(
            linea1,
            True,
            (255, 255, 255)
        )

        pantalla.blit(
            texto1,
            (
                12,
                y0 + 8
            )
        )

        # ----------------------------------------------------
        # Segunda línea: uso de salidas
        # ----------------------------------------------------

        linea2 = (
            f"A: {uso_salidas.get((0, 8), 0)}"
            f"    "
            f"B: {uso_salidas.get((29, 8), 0)}"
            f"    "
            f"C: {uso_salidas.get((15, 5), 0)}"
            f"    "
            f"D: {uso_salidas.get((15, 11), 0)}"
        )

        if self.terminada:
            linea2 += (
                f"    |    EVACUACIÓN COMPLETA"
                f" en {self.tiempo_final:.1f} s"
                f"    |    R = reiniciar"
            )

            color2 = (
                100,
                230,
                120
            )

        else:
            linea2 += (
                f"    |    ESC = salir"
                f"    R = reiniciar"
            )

            color2 = (
                230,
                230,
                235
            )

        texto2 = self.fuente.render(
            linea2,
            True,
            color2
        )

        pantalla.blit(
            texto2,
            (
                12,
                y0 + 34
            )
        )
