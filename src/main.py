from emergency.scenario import EmergencyScenario
from evacuation.person import Person
from evacuation.grid import Grid
from evacuation.astar import AStar


def main():
    scenario = EmergencyScenario(
        emergency_type="incendio",
        zone="laboratorio",
        people=30,
        blocked_exit="norte"
    )

    person = Person(
        person_id=1,
        position=(0, 0),
        target_exit=(4, 4)
    )

    grid = Grid(5, 5)

    grid.set_obstacle(2, 0)
    grid.set_obstacle(2, 1)
    grid.set_obstacle(2, 2)

    astar = AStar(grid)

    route = astar.find_path(
        person.position,
        person.target_exit
    )

    person.set_route(route)

    print("Simulador de Evacuación Inteligente")
    print("-----------------------------------")
    print(scenario)
    print()
    print(person)
    print()
    print("Mapa:")
    print(grid)
    print()
    print("Ruta encontrada:")
    print(person.route)


if __name__ == "__main__":
    main()