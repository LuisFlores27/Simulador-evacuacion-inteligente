
### Instalar Ollama y el modelo

1. Descarguen e instalen Ollama desde [ollama.com/download](https://ollama.com/download).
2. Abran Ollama desde el menú Inicio y déjenlo ejecutándose.
3. Abran PowerShell y descarguen el modelo que usa el proyecto:

ollama pull llama3.2
ollama list

Esperen a que termine la descarga. Háganla una sola vez en cada computadora; `ollama list` debe mostrar `llama3.2` antes de usar la IA.

### Iniciar el simulador

Con Ollama ejecutándose y el entorno `.venv` activado, inicien el simulador:

python src\main.py

Antes de entrar al proyecto, ejecuten la app de Ollama y luego ahora si abran el proyecto.

## Si Ollama no conecta

- Comprueben que Ollama esté abierto y que `ollama list` muestre `llama3.2`.
- Si PowerShell dice que `ollama` no se reconoce, instalen Ollama y abran una nueva ventana de PowerShell.
- Si Ollama está instalado pero el servicio no inició, ejecuten `ollama serve` en una terminal. No lo ejecuten si Ollama ya está atendiendo solicitudes.
- La aplicación usa por defecto `http://localhost:11434/v1/chat/completions` y el modelo `llama3.2`.
- La IA local no requiere una API key.

## Organización del código

- `src/ui/interfaz.py`: pantalla inicial, editor de instrucciones, interacción de teclado y mouse, botones, previsualización y panel de evacuación.
- `src/graphics/graficos.py`: dibujo del edificio y las personas, animación y coordinación visual de la simulación.
- `src/graphics/config.py`: dimensiones compartidas del mapa y del lienzo.
- `src/evacuation/` y `src/emergency/`: rutas, movimiento y reglas de los escenarios; la separación de la interfaz no cambia esta lógica.
