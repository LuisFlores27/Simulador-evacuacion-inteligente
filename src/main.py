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
            pantalla
        )

        pygame.display.flip()

    pygame.quit()
    simulacion.ai_executor.shutdown(
        wait=False,
        cancel_futures=True
    )


if __name__ == "__main__":
    main()