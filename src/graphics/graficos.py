"""
Simulación visual
"""
import heapq
import math
import random
import sys

import pygame

# Base gráfica y coordenadas
TILE = 32
COLS, ROWS = 30, 18
PANEL = 64                      # franja inferior con leyenda y datos
ANCHO, ALTO = COLS * TILE, ROWS * TILE + PANEL
FPS = 60


def casilla_a_pixel(col, fila):
    return col * TILE, fila * TILE


def centro(col, fila):
    return col * TILE + TILE // 2, fila * TILE + TILE // 2


# Edificio
PARED, PISO, PASILLO, PUERTA, SALIDA = "#", ".", ",", "D", "E"
CAMINABLES = {PISO, PASILLO, PUERTA, SALIDA}

COLORES = {
    PARED: (60, 60, 70),
    PISO: (225, 225, 215),
    PASILLO: (190, 195, 205),
    PUERTA: (150, 100, 50),
    SALIDA: (60, 180, 90),
}

HABITACIONES = [
    (1, 1, 6, 4, "Laboratorio"), (8, 1, 7, 4, "Aula 1"),
    (16, 1, 7, 4, "Aula 2"), (24, 1, 5, 4, "Oficina"),
    (1, 12, 6, 5, "Biblioteca"), (8, 12, 7, 5, "Aula 3"),
    (16, 12, 7, 5, "Aula 4"), (24, 12, 5, 5, "Sala"),
]

# Salidas: casilla -> letra
SALIDAS = {(0, 8): "A", (29, 8): "B", (15, 5): "C", (15, 11): "D"}

# ESCENARIO
SALIDAS_BLOQUEADAS = {(29, 8), (15, 5)}
ZONA_FUEGO = {(c, f) for c in range(26, 29) for f in range(7, 10)}

COLOR_SALIDA = {"A": (30, 120, 230), "B": (120, 120, 120),
                "C": (120, 120, 120), "D": (170, 60, 200)}


class Edificio:
    def __init__(self):
        self.grid = [[PARED] * COLS for _ in range(ROWS)]
        for (c, f, w, h, _) in HABITACIONES:
            for j in range(f, f + h):
                for i in range(c, c + w):
                    self.grid[j][i] = PISO
        for j in range(6, 11):
            for i in range(1, COLS - 1):
                self.grid[j][i] = PASILLO
        for (c, f, w, h, _) in HABITACIONES:
            fila_puerta = 5 if f < 6 else 11
            self.grid[fila_puerta][c + w // 2] = PUERTA
        for (c, f) in SALIDAS:
            self.grid[f][c] = SALIDA
        self.bloqueadas = set(SALIDAS_BLOQUEADAS)
        self.fuego = set(ZONA_FUEGO)
        self.fuente = pygame.font.SysFont("arial", 14, bold=True)

    def caminable(self, col, fila):
        return (0 <= col < COLS and 0 <= fila < ROWS
                and self.grid[fila][col] in CAMINABLES
                and (col, fila) not in self.bloqueadas
                and (col, fila) not in self.fuego)

    def salidas_abiertas(self):
        return [s for s in SALIDAS if s not in self.bloqueadas]

    def dibujar(self, pantalla, t):
        for fila in range(ROWS):
            for col in range(COLS):
                x, y = casilla_a_pixel(col, fila)
                rect = pygame.Rect(x, y, TILE, TILE)
                pygame.draw.rect(pantalla, COLORES[self.grid[fila][col]], rect)
                if self.grid[fila][col] != PARED:
                    pygame.draw.rect(pantalla, (170, 170, 175), rect, 1)
        # Fuego (parpadea)
        for (c, f) in self.fuego:
            x, y = casilla_a_pixel(c, f)
            v = math.sin(t * 8 + c * 1.7 + f * 2.3)
            color = (235, int(110 + 50 * v), 20)
            pygame.draw.rect(pantalla, color, (x, y, TILE, TILE))
        # Salidas
        for (c, f), letra in SALIDAS.items():
            x, y = casilla_a_pixel(c, f)
            bloq = (c, f) in self.bloqueadas
            pygame.draw.rect(pantalla, (200, 40, 40) if bloq else (60, 180, 90),
                             (x, y, TILE, TILE))
            if bloq:
                pygame.draw.line(pantalla, (255, 255, 255), (x + 6, y + 6),
                                 (x + TILE - 6, y + TILE - 6), 4)
                pygame.draw.line(pantalla, (255, 255, 255), (x + TILE - 6, y + 6),
                                 (x + 6, y + TILE - 6), 4)
            else:
                txt = self.fuente.render(letra, True, (255, 255, 255))
                pantalla.blit(txt, (x + 11, y + 7))
        # Nombres de habitaciones
        for (c, f, w, h, nombre) in HABITACIONES:
            txt = self.fuente.render(nombre, True, (80, 80, 90))
            pantalla.blit(txt, (c * TILE + 6, f * TILE + 4))


# Rutas (A* temporal)
def a_estrella(edificio, inicio, meta):
    def h(p):
        return abs(p[0] - meta[0]) + abs(p[1] - meta[1])

    cola = [(h(inicio), 0, inicio)]
    previo = {inicio: None}
    costo = {inicio: 0}
    while cola:
        _, g, act = heapq.heappop(cola)
        if act == meta:
            ruta = []
            while act is not None:
                ruta.append(act)
                act = previo[act]
            return ruta[::-1]
        for dc, df in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sig = (act[0] + dc, act[1] + df)
            if not edificio.caminable(*sig):
                continue
            ng = g + 1
            if ng < costo.get(sig, 10 ** 9):
                costo[sig] = ng
                previo[sig] = act
                heapq.heappush(cola, (ng + h(sig), ng, sig))
    return None


def mejor_ruta(edificio, inicio):
    """Devuelve (ruta, salida) hacia la salida abierta más corta."""
    mejor, meta = None, None
    for s in edificio.salidas_abiertas():
        r = a_estrella(edificio, inicio, s)
        if r and (mejor is None or len(r) < len(mejor)):
            mejor, meta = r, s
    return mejor, meta

class Persona:
    def __init__(self, col, fila, edificio):
        self.col, self.fila = col, fila
        self.x, self.y = casilla_a_pixel(col, fila)
        ruta, self.salida = mejor_ruta(edificio, (col, fila))
        self.ruta = ruta[1:] if ruta else []
        self.destino = None
        self.velocidad = 75
        self.retraso = random.uniform(0, 3)   # tiempo de reacción
        self.fase = random.random() * 6.28
        self.evacuado = False
        self.tiempo_salida = None
        letra = SALIDAS.get(self.salida)
        self.color = COLOR_SALIDA[letra] if letra else (90, 90, 90)

    @property
    def moviendo(self):
        return self.destino is not None

    def actualizar(self, dt, t):
        if self.evacuado:
            return
        if self.retraso > 0:
            self.retraso -= dt
            return
        if self.destino is None:
            if not self.ruta:
                return
            self.destino = self.ruta.pop(0)
        tx, ty = casilla_a_pixel(*self.destino)
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        paso = self.velocidad * dt
        if dist <= paso:
            self.x, self.y = tx, ty
            self.col, self.fila = self.destino
            self.destino = None
            if (self.col, self.fila) == self.salida:
                self.evacuado = True
                self.tiempo_salida = t
        else:
            self.x += dx / dist * paso
            self.y += dy / dist * paso
            self.fase += dt * 14

    def puntos_ruta(self):
        pts = [(int(self.x + TILE / 2), int(self.y + TILE / 2))]
        if self.destino:
            pts.append(centro(*self.destino))
        pts += [centro(c, f) for (c, f) in self.ruta]
        return pts

    def dibujar(self, pantalla):
        if self.evacuado:
            return
        cx = int(self.x + TILE / 2)
        base = int(self.y + TILE - 3)
        b = math.sin(self.fase) * 5 if self.moviendo else 0
        r = abs(math.sin(self.fase)) * 2 if self.moviendo else 0
        pygame.draw.line(pantalla, (40, 40, 50), (cx - 3, base - 8 - r),
                         (cx - 3 + b, base), 3)
        pygame.draw.line(pantalla, (40, 40, 50), (cx + 3, base - 8 - r),
                         (cx + 3 - b, base), 3)
        pygame.draw.rect(pantalla, self.color, (cx - 5, base - 21 - r, 10, 13),
                         border_radius=3)
        pygame.draw.circle(pantalla, (240, 205, 170), (cx, int(base - 26 - r)), 6)


# Simulación y panel
class Simulacion:
    def __init__(self):
        self.edificio = Edificio()
        self.personas = []
        for (c, f, w, h, _) in HABITACIONES:
            celdas = [(i, j) for j in range(f, f + h) for i in range(c, c + w)
                      if self.edificio.caminable(i, j)]
            for (i, j) in random.sample(celdas, 3):
                self.personas.append(Persona(i, j, self.edificio))
        self.tiempo = 0.0
        self.fin = None
        self.capa = pygame.Surface((COLS * TILE, ROWS * TILE), pygame.SRCALPHA)
        self.fuente = pygame.font.SysFont("arial", 15, bold=True)

    def actualizar(self, dt):
        if self.fin is None:
            self.tiempo += dt
        for p in self.personas:
            p.actualizar(dt, self.tiempo)
        con_ruta = [p for p in self.personas if p.salida]
        if self.fin is None and all(p.evacuado for p in con_ruta):
            self.fin = self.tiempo

    def dibujar(self, pantalla):
        self.edificio.dibujar(pantalla, self.tiempo)
        # Rutas de evacuación (semitransparentes)
        self.capa.fill((0, 0, 0, 0))
        for p in self.personas:
            if p.evacuado or not p.salida:
                continue
            pts = p.puntos_ruta()
            if len(pts) > 1:
                pygame.draw.lines(self.capa, p.color + (150,), False, pts, 3)
        pantalla.blit(self.capa, (0, 0))
        for p in self.personas:
            p.dibujar(pantalla)
        self.dibujar_panel(pantalla)

    def dibujar_panel(self, pantalla):
        y0 = ROWS * TILE
        pygame.draw.rect(pantalla, (28, 30, 38), (0, y0, ANCHO, PANEL))
        # Leyenda
        items = [((60, 180, 90), "Salida abierta"), ((200, 40, 40), "Salida bloqueada"),
                 ((235, 130, 20), "Fuego"), (COLOR_SALIDA["A"], "Ruta a A"),
                 (COLOR_SALIDA["D"], "Ruta a D")]
        x = 12
        for color, texto in items:
            pygame.draw.rect(pantalla, color, (x, y0 + 10, 14, 14))
            t = self.fuente.render(texto, True, (230, 230, 235))
            pantalla.blit(t, (x + 20, y0 + 8))
            x += 20 + t.get_width() + 22
        # Datos
        total = len([p for p in self.personas if p.salida])
        listos = len([p for p in self.personas if p.evacuado])
        abiertas = ", ".join(SALIDAS[s] for s in self.edificio.salidas_abiertas())
        cerradas = ", ".join(SALIDAS[s] for s in sorted(self.edificio.bloqueadas, key=SALIDAS.get))
        linea = (f"Evacuados: {listos}/{total}    Tiempo: {self.tiempo:4.1f} s    "
                 f"Abiertas: {abiertas}    Bloqueadas: {cerradas}")
        if self.fin is not None:
            linea += f"    EVACUACIÓN COMPLETA en {self.fin:.1f} s  (R = reiniciar)"
        pantalla.blit(self.fuente.render(linea, True, (255, 255, 255)), (12, y0 + 36))


def main():
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Simulador de evacuación inteligente")
    reloj = pygame.time.Clock()
    sim = Simulacion()

    while True:
        dt = min(reloj.tick(FPS) / 1000, 0.05)
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN
                                         and e.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_r:
                sim = Simulacion()
        sim.actualizar(dt)
        sim.dibujar(pantalla)
        pygame.display.flip()


if __name__ == "__main__":
    main()
