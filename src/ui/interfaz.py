import math

import pygame

from emergency.scenario import EmergencyScenario
from graphics.config import (
    ALTO,
    ANCHO,
    COLS,
    TILE,
    TILE_X,
    TOTAL_ROWS,
)


PREVIEW_BUTTON = pygame.Rect(88, 520, 300, 58)
INSTRUCTION_TOP = 360
INSTRUCTION_MIN_HEIGHT = 72
INSTRUCTION_MAX_HEIGHT = 260
PREVIEW_BACK_BUTTON = pygame.Rect(
    ANCHO - 268,
    ALTO - 76,
    220,
    56,
)

COLORS = {
    "background": (12, 18, 30),
    "background_soft": (19, 28, 44),
    "surface": (25, 36, 54),
    "surface_light": (34, 47, 68),
    "border": (57, 75, 101),
    "text": (238, 244, 252),
    "muted": (151, 168, 190),
    "accent": (73, 184, 255),
    "accent_soft": (36, 114, 173),
    "green": (59, 205, 143),
    "amber": (247, 183, 74),
    "red": (255, 101, 105),
    "floor": (239, 244, 249),
    "floor_alt": (232, 239, 246),
    "corridor": (216, 226, 237),
    "wall": (27, 39, 57),
    "wall_line": (44, 60, 82),
}


class Interfaz:

    @staticmethod
    def _selection_rect(start, end):
        return (min(start, end), max(start, end))

    def _wrapped_instruction_lines(self, font, width):
        lines = []
        start = 0
        while start <= len(self.instruccion):
            if start == len(self.instruccion):
                lines.append((start, start))
                break

            end = start
            last_space = None
            while end < len(self.instruccion) and self.instruccion[end] != "\n":
                if font.size(self.instruccion[start:end + 1])[0] > width:
                    break
                if self.instruccion[end].isspace():
                    last_space = end
                end += 1

            if end == len(self.instruccion):
                lines.append((start, end))
                break
            if self.instruccion[end] == "\n":
                lines.append((start, end))
                start = end + 1
            elif last_space is not None and last_space > start:
                lines.append((start, last_space + 1))
                start = last_space + 1
            else:
                if end == start:
                    end += 1
                lines.append((start, end))
                start = end

        return lines

    def _prompt_layout(self, font):
        margin = 12
        field_width = 832
        text_width = field_width - margin * 2
        lines = self._wrapped_instruction_lines(font, text_width)
        line_height = font.get_linesize() + 4
        field_height = min(
            max(INSTRUCTION_MIN_HEIGHT, len(lines) * line_height + 16),
            INSTRUCTION_MAX_HEIGHT,
        )
        field = pygame.Rect(
            88,
            INSTRUCTION_TOP,
            field_width,
            field_height,
        )
        button = PREVIEW_BUTTON.copy()
        button.top = max(PREVIEW_BUTTON.y, field.bottom + 44)
        button.top = min(button.top, ALTO - button.height - 12)

        visible_line_count = max(1, (field.height - 16) // line_height)
        cursor_line = len(lines) - 1
        for index, (start, end) in enumerate(lines):
            if start <= self.cursor_instruccion < end:
                cursor_line = index
                break
            if self.cursor_instruccion == start:
                cursor_line = index
                break
        first_visible_line = min(
            max(0, cursor_line - visible_line_count + 1),
            max(0, len(lines) - visible_line_count),
        )
        return field, button, lines, line_height, first_visible_line, visible_line_count

    def _instruction_cursor_at(self, position, font):
        field, _, lines, line_height, first_visible_line, visible_line_count = (
            self._prompt_layout(font)
        )
        if not field.collidepoint(position):
            return None

        text_left = field.x + 12
        text_top = field.y + 8
        visible_index = round((position[1] - text_top) / line_height)
        visible_index = min(
            max(visible_index, 0),
            visible_line_count - 1,
        )
        line_index = min(
            first_visible_line + visible_index,
            len(lines) - 1,
        )
        start, end = lines[line_index]
        line_text = self.instruccion[start:end]
        relative_x = max(0, position[0] - text_left)
        cursor = start
        for offset in range(1, len(line_text) + 1):
            left_width = font.size(line_text[:offset - 1])[0]
            right_width = font.size(line_text[:offset])[0]
            if relative_x < (left_width + right_width) / 2:
                break
            cursor = start + offset
        return cursor

    def _replace_selection(self, text):
        if self.selection_anchor is None:
            start = end = self.cursor_instruccion
        else:
            start, end = self._selection_rect(
                self.selection_anchor,
                self.cursor_instruccion,
            )
        inserted = text
        self.instruccion = (
            self.instruccion[:start]
            + inserted
            + self.instruccion[end:]
        )
        self.cursor_instruccion = start + len(inserted)
        self.selection_anchor = None

    def _clipboard_text(self):
        try:
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            content = pygame.scrap.get(pygame.SCRAP_TEXT)
        except pygame.error as error:
            self.estado_ia = f"No se pudo leer el portapapeles: {error}"
            return ""
        if not content:
            return ""
        if isinstance(content, bytes):
            return content.rstrip(b"\0").decode("utf-8", errors="replace")
        return str(content).rstrip("\0")

    def _handle_text_shortcut(self, evento):
        modifiers = getattr(evento, "mod", pygame.key.get_mods())
        if not modifiers & pygame.KMOD_CTRL:
            return False

        if evento.key == pygame.K_v:
            self._replace_selection(self._clipboard_text())
            return True

        if evento.key == pygame.K_a:
            self.selection_anchor = 0
            self.cursor_instruccion = len(self.instruccion)
        elif evento.key == pygame.K_c:
            start, end = (
                self._selection_rect(
                    self.selection_anchor,
                    self.cursor_instruccion,
                )
                if self.selection_anchor is not None
                else (0, len(self.instruccion))
            )
            try:
                if not pygame.scrap.get_init():
                    pygame.scrap.init()
                pygame.scrap.put(
                    pygame.SCRAP_TEXT,
                    self.instruccion[start:end].encode("utf-8"),
                )
            except pygame.error as error:
                self.estado_ia = f"No se pudo copiar al portapapeles: {error}"
        elif evento.key == pygame.K_x:
            start, end = (
                self._selection_rect(
                    self.selection_anchor,
                    self.cursor_instruccion,
                )
                if self.selection_anchor is not None
                else (0, len(self.instruccion))
            )
            try:
                if not pygame.scrap.get_init():
                    pygame.scrap.init()
                pygame.scrap.put(
                    pygame.SCRAP_TEXT,
                    self.instruccion[start:end].encode("utf-8"),
                )
            except pygame.error as error:
                self.estado_ia = f"No se pudo cortar al portapapeles: {error}"
                return True
            self.instruccion = self.instruccion[:start] + self.instruccion[end:]
            self.cursor_instruccion = start
            self.selection_anchor = None
        else:
            return False
        return True

    def manejar_evento(self, evento):
        if evento.type == pygame.MOUSEBUTTONDOWN and evento.button == 1:
            position = getattr(evento, "logical_pos", evento.pos)
            if self.preview_mode:
                if PREVIEW_BACK_BUTTON.collidepoint(position):
                    self.preview_mode = False
                    if self.inicio_pendiente and self.input_mode:
                        pygame.key.start_text_input()
                return
            if self.inicio_pendiente:
                prompt_font = pygame.font.SysFont("arial", 21)
                field, preview_button, _, _, _, _ = self._prompt_layout(
                    prompt_font
                )
                if field.collidepoint(position) and self.input_mode:
                    self.cursor_instruccion = (
                        self._instruction_cursor_at(position, prompt_font)
                    )
                    self.selection_anchor = None
                    pygame.key.start_text_input()
                    return
                if preview_button.collidepoint(position):
                    self.preview_mode = True
                    pygame.key.stop_text_input()
                    return
        if self.preview_mode:
            if evento.type == pygame.KEYDOWN and evento.key == pygame.K_ESCAPE:
                self.preview_mode = False
                if self.inicio_pendiente and self.input_mode:
                    pygame.key.start_text_input()
            return

        if evento.type == pygame.TEXTINPUT and self.input_mode:
            self._replace_selection(evento.text)
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
            if self._handle_text_shortcut(evento):
                return
            shift_held = bool(
                getattr(evento, "mod", pygame.key.get_mods()) & pygame.KMOD_SHIFT
            )
            if evento.key not in {pygame.K_LEFT, pygame.K_RIGHT, pygame.K_HOME, pygame.K_END}:
                self.selection_anchor = None
            if evento.key in escenarios_inicio:
                self.aplicar_escenario(escenarios_inicio[evento.key])
            elif evento.key == pygame.K_ESCAPE:
                if self.inicio_pendiente:
                    self.estado_ia = "Escribe una emergencia indicando el piso."
                else:
                    self.input_mode = False
                    self.instruccion = ""
                    self.cursor_instruccion = 0
                    pygame.key.stop_text_input()
                    self.estado_ia = "Entrada cancelada. Usa 1-4 para escenarios locales."
            elif evento.key == pygame.K_BACKSPACE:
                if self.selection_anchor is not None:
                    self._replace_selection("")
                elif self.cursor_instruccion:
                    self.instruccion = (
                        self.instruccion[:self.cursor_instruccion - 1]
                        + self.instruccion[self.cursor_instruccion:]
                    )
                    self.cursor_instruccion -= 1
            elif evento.key == pygame.K_DELETE:
                if self.selection_anchor is not None:
                    self._replace_selection("")
                else:
                    self.instruccion = (
                        self.instruccion[:self.cursor_instruccion]
                        + self.instruccion[self.cursor_instruccion + 1:]
                    )
            elif evento.key == pygame.K_LEFT:
                if shift_held and self.selection_anchor is None:
                    self.selection_anchor = self.cursor_instruccion
                if not shift_held and self.selection_anchor is not None:
                    self.cursor_instruccion = min(
                        self.selection_anchor,
                        self.cursor_instruccion,
                    )
                    self.selection_anchor = None
                else:
                    self.cursor_instruccion = max(0, self.cursor_instruccion - 1)
            elif evento.key == pygame.K_RIGHT:
                if shift_held and self.selection_anchor is None:
                    self.selection_anchor = self.cursor_instruccion
                if not shift_held and self.selection_anchor is not None:
                    self.cursor_instruccion = max(
                        self.selection_anchor,
                        self.cursor_instruccion,
                    )
                    self.selection_anchor = None
                else:
                    self.cursor_instruccion = min(
                        len(self.instruccion),
                        self.cursor_instruccion + 1,
                    )
            elif evento.key == pygame.K_HOME:
                if shift_held and self.selection_anchor is None:
                    self.selection_anchor = self.cursor_instruccion
                self.cursor_instruccion = 0
            elif evento.key == pygame.K_END:
                if shift_held and self.selection_anchor is None:
                    self.selection_anchor = self.cursor_instruccion
                self.cursor_instruccion = len(self.instruccion)
            elif (
                evento.key == pygame.K_RETURN
                and getattr(evento, "mod", 0) & pygame.KMOD_SHIFT
            ):
                self._replace_selection("\n")
            elif evento.key == pygame.K_RETURN:
                self.enviar_instruccion()
            return

        if evento.key == pygame.K_r and self.terminada:
            self.reiniciar_simulacion()
            return

        if evento.key == pygame.K_b:
            self.volver_a_inicio()
            return

        if evento.key in escenarios_locales:
            self.aplicar_escenario(escenarios_locales[evento.key])
        elif evento.key in escenarios_inicio:
            self.aplicar_escenario(escenarios_inicio[evento.key])

    def dibujar_inicio(self, pantalla):
        pantalla.fill(COLORS["background"])
        titulo = pygame.font.SysFont("arial", 48, bold=True)
        texto = pygame.font.SysFont("arial", 20)
        etiqueta = pygame.font.SysFont("arial", 14, bold=True)
        (
            campo,
            boton_previsualizacion,
            lineas_instruccion,
            alto_linea,
            primera_linea_visible,
            cantidad_lineas_visibles,
        ) = self._prompt_layout(texto)
        for x in range(24, ANCHO, 64):
            pygame.draw.line(pantalla, (17, 29, 46), (x, 0), (x, ALTO), 1)
        for y in range(24, ALTO, 64):
            pygame.draw.line(pantalla, (17, 29, 46), (0, y), (ANCHO, y), 1)
        pygame.draw.rect(
            pantalla,
            (7, 13, 23),
            (64, 250, 880, 660),
            border_radius=24,
        )
        pygame.draw.rect(
            pantalla,
            COLORS["surface"],
            (64, 242, 880, 660),
            border_radius=24,
        )
        pygame.draw.rect(
            pantalla,
            COLORS["border"],
            (64, 242, 880, 660),
            width=1,
            border_radius=24,
        )
        pygame.draw.rect(
            pantalla,
            (7, 13, 23),
            (992, 250, 864, 660),
            border_radius=24,
        )
        pygame.draw.rect(
            pantalla,
            COLORS["surface"],
            (992, 242, 864, 660),
            border_radius=24,
        )
        pygame.draw.rect(
            pantalla,
            COLORS["border"],
            (992, 242, 864, 660),
            width=1,
            border_radius=24,
        )
        self._dibujar_motivo_edificio(pantalla)
        pygame.draw.rect(
            pantalla,
            COLORS["surface"],
            (16, 24, ANCHO - 32, 148),
            border_radius=18,
        )
        pygame.draw.rect(
            pantalla,
            COLORS["border"],
            (16, 24, ANCHO - 32, 148),
            width=1,
            border_radius=18,
        )
        pygame.draw.rect(
            pantalla,
            COLORS["accent"],
            (24, 42, 4, 92),
            border_radius=2,
        )
        pulse = (math.sin(pygame.time.get_ticks() / 750) + 1) / 2
        pygame.draw.circle(
            pantalla,
            (61, 190 + round(pulse * 45), 165 + round(pulse * 35)),
            (42, 48),
            6,
        )
        chip = etiqueta.render("CENTRO DE CONTROL  /  EVACUACIÓN", True, COLORS["accent"])
        pantalla.blit(chip, (60, 42))
        title_surface = titulo.render("Evacuación inteligente", True, COLORS["text"])
        pantalla.blit(title_surface, (42, 66))
        subtitle = texto.render(
            "Simula emergencias. Visualiza rutas seguras. Protege cada vida.",
            True,
            COLORS["muted"],
        )
        pantalla.blit(subtitle, (44, 121))

        card_title = pygame.font.SysFont("arial", 24, bold=True).render(
            "Diseña tu escenario",
            True,
            COLORS["text"],
        )
        pantalla.blit(card_title, (88, 282))
        field_label = etiqueta.render("DESCRIBE LA EMERGENCIA", True, COLORS["muted"])
        pantalla.blit(field_label, (88, 326))
        pygame.draw.rect(
            pantalla,
            (14, 23, 37),
            campo,
            border_radius=12,
        )
        pygame.draw.rect(
            pantalla,
            COLORS["accent"] if self.input_mode else COLORS["border"],
            campo,
            width=1,
            border_radius=12,
        )

        margen = 12
        clip_anterior = pantalla.get_clip()
        pantalla.set_clip(campo.inflate(-margen, -8))
        texto_x = campo.x + margen
        text_top = campo.y + 8
        if not self.instruccion:
            placeholder = texto.render(
                "Ej.: Incendio en el laboratorio del segundo piso; evacúa a 24 personas.",
                True,
                COLORS["muted"],
            )
            pantalla.blit(placeholder, (texto_x, text_top))
        selection_start, selection_end = (
            self._selection_rect(
                self.selection_anchor,
                self.cursor_instruccion,
            )
            if self.selection_anchor is not None
            else (self.cursor_instruccion, self.cursor_instruccion)
        )
        cursor_position = None
        for visible_index in range(cantidad_lineas_visibles):
            line_index = primera_linea_visible + visible_index
            if line_index >= len(lineas_instruccion):
                break
            start, end = lineas_instruccion[line_index]
            line_text = self.instruccion[start:end]
            texto_y = text_top + visible_index * alto_linea

            selected_start = max(start, selection_start)
            selected_end = min(end, selection_end)
            if selected_start < selected_end:
                selection_x = texto_x + texto.size(
                    self.instruccion[start:selected_start]
                )[0]
                selection_width = texto.size(
                    self.instruccion[selected_start:selected_end]
                )[0]
                pygame.draw.rect(
                    pantalla,
                    (52, 97, 143),
                    (
                        selection_x,
                        texto_y,
                        selection_width,
                        texto.get_linesize(),
                    ),
                )
            line_surface = texto.render(line_text, True, COLORS["text"])
            pantalla.blit(line_surface, (texto_x, texto_y))

            if start <= self.cursor_instruccion <= end:
                cursor_position = (
                    texto_x
                    + texto.size(
                        self.instruccion[start:self.cursor_instruccion]
                    )[0],
                    texto_y,
                )

        if (
            self.input_mode
            and cursor_position is not None
            and pygame.time.get_ticks() // 500 % 2 == 0
        ):
            cursor_x, cursor_y = cursor_position
            pygame.draw.line(
                pantalla,
                COLORS["accent"],
                (cursor_x, cursor_y),
                (cursor_x, cursor_y + texto.get_linesize()),
                2,
            )
        pantalla.set_clip(clip_anterior)

        status_y = campo.bottom + 14
        if self.ai_future is not None:
            loading_font = pygame.font.SysFont("arial", 19, bold=True)
            dots = "." * (pygame.time.get_ticks() // 350 % 4)
            loading = loading_font.render(
                f"Cargando instrucción{dots}",
                True,
                COLORS["accent"],
            )
            pantalla.blit(loading, (88, status_y))
        elif self.error_ia:
            error_font = pygame.font.SysFont("arial", 17)
            error_text = self.error_ia
            while (
                error_text
                and error_font.size(error_text)[0] > campo.width
            ):
                error_text = error_text[:-2] + "…"
            error_surface = error_font.render(
                error_text,
                True,
                COLORS["red"],
            )
            pantalla.blit(error_surface, (88, status_y))
        else:
            helper_font = pygame.font.SysFont("arial", 16)
            helper = helper_font.render(
                "Indica el tipo de emergencia y el piso. Pulsa Enter para generar.",
                True,
                COLORS["muted"],
            )
            pantalla.blit(helper, (88, status_y))

        self._dibujar_boton(
            pantalla,
            boton_previsualizacion,
            "PREVISUALIZAR ESCENARIO",
            COLORS["accent_soft"],
        )
        shortcut_label = etiqueta.render("ATAJOS RÁPIDOS", True, COLORS["muted"])
        pantalla.blit(shortcut_label, (88, 770))
        shortcut_font = pygame.font.SysFont("arial", 16, bold=True)
        for index, (key, name, color) in enumerate(
            (
                ("1", "Incendio", COLORS["red"]),
                ("2", "Zona peligrosa", COLORS["amber"]),
                ("3", "Salida bloqueada", COLORS["accent"]),
                ("4", "Combinada", COLORS["green"]),
            )
        ):
            x = 88 + index * 205
            chip = pygame.Rect(x, 800, 190, 42)
            pygame.draw.rect(
                pantalla,
                COLORS["background_soft"],
                chip,
                border_radius=10,
            )
            pygame.draw.circle(pantalla, color, (x + 22, 821), 5)
            pantalla.blit(
                shortcut_font.render(f"{key}  {name}", True, COLORS["text"]),
                (x + 36, 810),
            )

    def _dibujar_motivo_edificio(self, pantalla):
        x = 1040
        floor_y_positions = (390, 650)
        heading = pygame.font.SysFont("arial", 26, bold=True).render(
            "El edificio, bajo control",
            True,
            COLORS["text"],
        )
        detail = pygame.font.SysFont("arial", 17).render(
            "Personas, plantas y salidas en seguimiento en tiempo real",
            True,
            COLORS["muted"],
        )
        pantalla.blit(heading, (x, 290))
        pantalla.blit(detail, (x, 329))
        for floor_index, y in enumerate(floor_y_positions):
            floor = pygame.Rect(x, y, 760, 184)
            pygame.draw.rect(
                pantalla,
                COLORS["background_soft"],
                floor,
                border_radius=12,
            )
            pygame.draw.rect(
                pantalla,
                COLORS["surface_light"],
                floor,
                width=1,
                border_radius=12,
            )
            for room in (
                pygame.Rect(x + 18, y + 20, 198, 62),
                pygame.Rect(x + 18, y + 102, 198, 62),
                pygame.Rect(x + 544, y + 20, 198, 62),
                pygame.Rect(x + 544, y + 102, 198, 62),
            ):
                pygame.draw.rect(
                    pantalla,
                    COLORS["surface"],
                    room,
                    border_radius=5,
                )
                pygame.draw.rect(
                    pantalla,
                    COLORS["border"],
                    room,
                    width=1,
                    border_radius=5,
                )

            corridor = pygame.Rect(x + 246, y + 18, 268, 148)
            pygame.draw.rect(
                pantalla,
                (29, 47, 68),
                corridor,
                border_radius=6,
            )
            pygame.draw.rect(
                pantalla,
                COLORS["accent_soft"],
                (x + 336, y + 59, 88, 58),
                border_radius=6,
            )
            for stair_y in range(y + 68, y + 112, 11):
                pygame.draw.line(
                    pantalla,
                    (177, 219, 250),
                    (x + 350, stair_y),
                    (x + 410, stair_y),
                    3,
                )

            for offset, color in (
                (0, COLORS["accent"]),
                (1, COLORS["green"]),
                (2, COLORS["amber"]),
            ):
                person_x = x + 286 + int(
                    (pygame.time.get_ticks() / 18 + offset * 120) % 180
                )
                pygame.draw.circle(
                    pantalla,
                    color,
                    (person_x, y + 92 + (offset % 2) * 22),
                    7,
                )

            floor_label = pygame.font.SysFont("arial", 14, bold=True).render(
                f"PISO {2 - floor_index}",
                True,
                COLORS["muted"],
            )
            pantalla.blit(floor_label, (x + 20, y - 25))
            if floor_index == 1:
                pygame.draw.rect(
                    pantalla,
                    COLORS["green"],
                    (x + 366, y + 169, 30, 8),
                    border_radius=3,
                )

        pygame.draw.line(
            pantalla,
            COLORS["accent_soft"],
            (x + 380, floor_y_positions[0] + 184),
            (x + 380, floor_y_positions[1]),
            3,
        )

    def _dibujar_boton(self, pantalla, rect, label, color):
        hovered = rect.collidepoint(
            getattr(self, "hover_position", (-1, -1))
        )
        draw_rect = rect.move(0, -2) if hovered else rect
        button_color = (
            tuple(min(255, channel + 18) for channel in color)
            if hovered
            else color
        )
        shadow = draw_rect.move(0, 4)
        pygame.draw.rect(
            pantalla,
            (6, 11, 20),
            shadow,
            border_radius=12,
        )
        pygame.draw.rect(pantalla, button_color, draw_rect, border_radius=12)
        pygame.draw.rect(
            pantalla,
            tuple(min(255, channel + 45) for channel in button_color),
            draw_rect,
            width=1,
            border_radius=12,
        )
        font = pygame.font.SysFont("arial", 18, bold=True)
        text = font.render(label, True, COLORS["text"])
        pantalla.blit(text, text.get_rect(center=draw_rect.center))

    def dibujar_previsualizacion(self, pantalla):
        pantalla.fill(COLORS["background"])
        map_x, map_y = 24, 0
        mapa = pygame.Surface((COLS * TILE_X, TOTAL_ROWS * TILE))
        self.edificio_previsualizacion.dibujar(mapa, 0)
        self.edificio_previsualizacion.dibujar_nombres_salidas(mapa)
        pygame.draw.rect(
            pantalla,
            COLORS["surface"],
            (map_x - 8, map_y - 8, mapa.get_width() + 16, mapa.get_height() + 16),
            border_radius=16,
        )
        pantalla.blit(mapa, (map_x, map_y))
        title_font = pygame.font.SysFont("arial", 28, bold=True)
        body_font = pygame.font.SysFont("arial", 17)
        pantalla.blit(
            title_font.render("Vista previa", True, COLORS["text"]),
            (1490, 76),
        )
        pantalla.blit(
            body_font.render(
                "Edificio de dos plantas",
                True,
                COLORS["muted"],
            ),
            (1492, 122),
        )
        pygame.draw.rect(
            pantalla,
            COLORS["surface"],
            (1480, 180, 416, 330),
            border_radius=18,
        )
        pantalla.blit(
            body_font.render(
                "Elementos del plano",
                True,
                COLORS["text"],
            ),
            (1506, 208),
        )
        for index, (label, color) in enumerate(
            (
                ("Salida disponible", COLORS["green"]),
                ("Escalera", (185, 202, 221)),
                ("Puerta", COLORS["amber"]),
            )
        ):
            item_y = 270 + index * 58
            pygame.draw.circle(pantalla, color, (1518, item_y + 10), 8)
            pantalla.blit(
                body_font.render(label, True, COLORS["muted"]),
                (1540, item_y),
            )
        self._dibujar_boton(
            pantalla,
            PREVIEW_BACK_BUTTON,
            "Volver",
            COLORS["accent_soft"],
        )

    def dibujar_panel(self, pantalla):
        panel = pygame.Rect(1480, 140, 416, 800)
        pygame.draw.rect(
            pantalla,
            (7, 13, 23),
            panel.move(0, 8),
            border_radius=24,
        )
        pygame.draw.rect(
            pantalla,
            COLORS["surface"],
            panel,
            border_radius=24,
        )
        pygame.draw.rect(
            pantalla,
            COLORS["border"],
            panel,
            width=1,
            border_radius=24,
        )

        resumen = self.manager.get_evacuation_summary()
        title_font = pygame.font.SysFont("arial", 22, bold=True)
        label_font = pygame.font.SysFont("arial", 13, bold=True)
        value_font = pygame.font.SysFont("arial", 36, bold=True)
        body_font = pygame.font.SysFont("arial", 15)

        def draw_text(text, font, color, position):
            pantalla.blit(font.render(text, True, color), position)

        draw_text("EVACUACIÓN", title_font, COLORS["text"], (1504, 164))
        status_text = "FINALIZADA" if self.terminada else "EN VIVO"
        status_color = COLORS["amber"] if self.terminada else COLORS["green"]
        pygame.draw.circle(pantalla, status_color, (1744, 177), 5)
        draw_text(status_text, label_font, status_color, (1756, 170))

        scenario_names = {
            "incendio": "Incendio",
            "zona_peligrosa": "Zona peligrosa",
            "salida_bloqueada": "Salida bloqueada",
            "combinada": "Emergencia combinada",
            "terremoto": "Terremoto",
        }
        scenario = scenario_names.get(
            self.escenario.emergency_type,
            self.escenario.emergency_type.replace("_", " ").title(),
        )
        draw_text(
            f"{scenario} · {self.escenario.zone}",
            body_font,
            COLORS["muted"],
            (1504, 208),
        )
        draw_text(
            f"Piso {self.escenario.floor} · {len(self.people)} personas",
            body_font,
            COLORS["muted"],
            (1504, 230),
        )

        people_card = pygame.Rect(1504, 270, 368, 116)
        pygame.draw.rect(
            pantalla,
            COLORS["background_soft"],
            people_card,
            border_radius=16,
        )
        pygame.draw.rect(
            pantalla,
            COLORS["border"],
            people_card,
            width=1,
            border_radius=16,
        )
        draw_text("PERSONAS EVACUADAS", label_font, COLORS["muted"], (1524, 288))
        draw_text(
            f"{resumen.people_evacuated:02d} / {resumen.total_people:02d}",
            value_font,
            COLORS["text"],
            (1524, 310),
        )
        if resumen.people_without_route:
            draw_text(
                f"{resumen.people_without_route} sin ruta",
                body_font,
                COLORS["red"],
                (1732, 346),
            )

        draw_text("PROGRESO", label_font, COLORS["muted"], (1504, 414))
        progress = (
            resumen.people_evacuated / resumen.total_people
            if resumen.total_people
            else 0
        )
        percent = pygame.font.SysFont("arial", 22, bold=True).render(
            f"{round(progress * 100)}%",
            True,
            COLORS["green"],
        )
        pantalla.blit(percent, (1814 - percent.get_width(), 408))
        progress_track = pygame.Rect(1504, 444, 368, 10)
        pygame.draw.rect(
            pantalla,
            COLORS["background_soft"],
            progress_track,
            border_radius=7,
        )
        if progress:
            progress_fill = progress_track.copy()
            progress_fill.width = max(14, round(progress_track.width * progress))
            pygame.draw.rect(
                pantalla,
                COLORS["green"],
                progress_fill,
                border_radius=7,
            )

        draw_text("SALIDAS", label_font, COLORS["muted"], (1504, 484))
        for index, (position, identifier) in enumerate(
            sorted(self.grid.exits.items(), key=lambda item: item[1])
        ):
            x = 1504 + (index % 2) * 188
            y = 512 + (index // 2) * 48
            blocked = position in self.grid.blocked_exits
            accent = COLORS["red"] if blocked else COLORS["green"]
            tile = pygame.Rect(x, y, 176, 38)
            pygame.draw.rect(
                pantalla,
                COLORS["background_soft"],
                tile,
                border_radius=10,
            )
            pygame.draw.circle(pantalla, accent, (x + 14, y + 19), 4)
            draw_text(
                f"{identifier} · {'BLOQ.' if blocked else 'LIBRE'}",
                label_font,
                accent,
                (x + 28, y + 12),
            )

        draw_text("TIEMPO", label_font, COLORS["muted"], (1504, 640))
        elapsed = self.tiempo_final if self.tiempo_final is not None else self.tiempo
        time_value = pygame.font.SysFont("arial", 27, bold=True).render(
            f"{elapsed:05.1f} s",
            True,
            COLORS["text"],
        )
        pantalla.blit(time_value, (1504, 664))
        if resumen.blocked_exits:
            draw_text(
                f"{resumen.blocked_exits} salida(s) bloqueada(s)",
                body_font,
                COLORS["red"],
                (1504, 710),
            )

        controls = pygame.Rect(1504, 770, 368, 102)
        pygame.draw.rect(
            pantalla,
            COLORS["background_soft"],
            controls,
            border_radius=14,
        )
        draw_text("ATAJOS", label_font, COLORS["accent"], (1524, 784))
        draw_text("B · Nuevo escenario", body_font, COLORS["text"], (1524, 810))
        draw_text(
            "1–4 · Escenarios rápidos",
            body_font,
            COLORS["muted"],
            (1524, 834),
        )
        if self.terminada:
            draw_text("R · Reiniciar", body_font, COLORS["muted"], (1748, 834))

        if self.terminada:
            status = (
                "EVACUACIÓN COMPLETA"
                if resumen.complete
                else "SIMULACIÓN FINALIZADA"
            )
            draw_text(
                status,
                label_font,
                COLORS["green"] if resumen.complete else COLORS["amber"],
                (1504, 738),
            )
