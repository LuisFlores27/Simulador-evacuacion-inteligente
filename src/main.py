import pygame

from graphics.graficos import (
    Simulacion,
    ANCHO,
    ALTO,
    FPS
)


def main():

    pygame.init()

    pantalla = pygame.display.set_mode(
        (ANCHO, ALTO)
    )

    pygame.display.set_caption(
        "Simulador de Evacuación Inteligente"
    )

    reloj = pygame.time.Clock()

    simulacion = Simulacion()

    ejecutando = True

    while ejecutando:

        dt = reloj.tick(FPS) / 1000.0

        # ----------------------------------------------------
        # Eventos
        # ----------------------------------------------------

        for evento in pygame.event.get():

            if evento.type == pygame.QUIT:
                ejecutando = False

            elif evento.type == pygame.KEYDOWN:

                if evento.key == pygame.K_ESCAPE:
                    ejecutando = False

                elif evento.key == pygame.K_r:
                    simulacion.reiniciar()

        # ----------------------------------------------------
        # Actualizar simulación
        # ----------------------------------------------------

        simulacion.actualizar(dt)

        # ----------------------------------------------------
        # Dibujar
        # ----------------------------------------------------

        simulacion.dibujar(
            pantalla
        )

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()