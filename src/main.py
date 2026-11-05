import pygame

from graphics.graficos import (
    Simulacion,
    ANCHO,
    ALTO,
    FPS
)


def main():

    pygame.init()
    pygame.key.set_repeat(400, 35)

    display_info = pygame.display.Info()
    ancho_escritorio = display_info.current_w or ANCHO
    alto_escritorio = display_info.current_h or ALTO
    tamano_ventana = (
        min(ANCHO, max(480, ancho_escritorio - 80)),
        min(ALTO, max(360, alto_escritorio - 100)),
    )
    pantalla = pygame.display.set_mode(tamano_ventana, pygame.RESIZABLE)
    lienzo = pygame.Surface((ANCHO, ALTO))

    pygame.display.set_caption(
        "Simulador de Evacuación Inteligente"
    )

    reloj = pygame.time.Clock()

    simulacion = Simulacion()
    pantalla_completa = False
    tamano_ventana_actual = tamano_ventana

    def canvas_position(position):
        screen_width, screen_height = pantalla.get_size()
        x = round(position[0] * ANCHO / screen_width)
        y = round(position[1] * ALTO / screen_height)
        if not (0 <= x < ANCHO and 0 <= y < ALTO):
            return (-1, -1)
        return (x, y)

    ejecutando = True

    while ejecutando:

        dt = reloj.tick(FPS) / 1000.0

        # ----------------------------------------------------
        # Eventos
        # ----------------------------------------------------

        for evento in pygame.event.get():
            if evento.type == pygame.MOUSEBUTTONDOWN:
                attributes = evento.dict.copy()
                attributes["logical_pos"] = canvas_position(evento.pos)
                evento = pygame.event.Event(evento.type, attributes)

            if evento.type == pygame.QUIT:
                ejecutando = False
            elif evento.type == pygame.KEYDOWN and evento.key == pygame.K_F11:
                if pantalla_completa:
                    pantalla = pygame.display.set_mode(
                        tamano_ventana_actual,
                        pygame.RESIZABLE,
                    )
                else:
                    tamano_ventana_actual = pantalla.get_size()
                    pantalla = pygame.display.set_mode(
                        (0, 0),
                        pygame.FULLSCREEN,
                    )
                pantalla_completa = not pantalla_completa
            elif evento.type == pygame.VIDEORESIZE:
                tamano_ventana_actual = evento.size
                pantalla = pygame.display.set_mode(
                    evento.size,
                    pygame.RESIZABLE,
                )
            else:
                estaba_escribiendo = simulacion.input_mode
                simulacion.manejar_evento(evento)

            if evento.type == pygame.KEYDOWN:
                if (
                    evento.key == pygame.K_ESCAPE
                    and not estaba_escribiendo
                ):
                    ejecutando = False

        # ----------------------------------------------------
        # Actualizar simulación
        # ----------------------------------------------------

        simulacion.actualizar(dt)

        # ----------------------------------------------------
        # Dibujar
        # ----------------------------------------------------

        simulacion.dibujar(
            lienzo
        )

        ancho, alto = pantalla.get_size()
        tamano_escala = (ancho, alto)
        imagen = pygame.transform.smoothscale(lienzo, tamano_escala)
        pantalla.fill((12, 14, 19))
        pantalla.blit(imagen, (0, 0))
        pygame.display.flip()

    pygame.quit()
    simulacion.ai_executor.shutdown(
        wait=False,
        cancel_futures=True
    )


if __name__ == "__main__":
    main()