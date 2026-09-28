from emergency.scenario import EmergencyScenario
from evacuation.person import create_random_people
from evacuation.grid import Grid
from evacuation.manager import EvacuationManager
from evacuation.exits import EXIT_POSITIONS


def main():
    scenario = EmergencyScenario(
        emergency_type="incendio",
        zone="laboratorio",
        people=30,
        blocked_exit="norte"
    )

    grid = Grid(5, 5)

    grid.set_obstacle(2, 0)
    grid.set_obstacle(2, 1)
    grid.set_obstacle(2, 2)

    grid.set_danger(1, 2)

    grid.set_exit(*EXIT_POSITIONS["norte"])
    grid.set_exit(*EXIT_POSITIONS["sur"])
    grid.set_exit(*EXIT_POSITIONS["oeste"])
    grid.set_exit(*EXIT_POSITIONS["este"])

    if scenario.blocked_exit:
        blocked_position = EXIT_POSITIONS.get(
            scenario.blocked_exit
        )

        if blocked_position:
            grid.block_exit(blocked_position)

    people = create_random_people(
        grid,
        scenario.people
    )

    evacuation = EvacuationManager(
        grid,
        people
    )

    evacuation.calculate_routes()

    summary = evacuation.get_evacuation_summary()

    print("Simulador de Evacuación Inteligente")
    print("-----------------------------------")
    print(scenario)
    print()

    print("Mapa:")
    print(grid)
    print()

    print("Salidas disponibles:")
    print(grid.get_exits())
    print()

    print("Personas:")
    print()

    for person in people:
        print(person)
        print("Ruta:", person.route)
        print()

    print("Resumen de evacuación:")
    print(
        f"Personas totales: "
        f"{summary['total_people']}"
    )

    print(
        f"Personas con ruta: "
        f"{summary['people_with_route']}"
    )


if __name__ == "__main__":
    main()