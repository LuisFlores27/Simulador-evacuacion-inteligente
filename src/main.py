from emergency.scenario import EmergencyScenario
from evacuation.person import Person
from evacuation.grid import Grid


def main():
    scenario = EmergencyScenario(
        emergency_type="incendio",
        zone="laboratorio",
        people=30,
        blocked_exit="norte"
    )

    person = Person(
        person_id=1,
        position=(2, 3)
    )

    person.set_route([
        (2, 3),
        (2, 4),
        (3, 4),
        (4, 4)
    ])

    grid = Grid(5, 5)

    grid.set_obstacle(2, 2)

    print("Simulador de Evacuación Inteligente")
    print("-----------------------------------")
    print(scenario)
    print()
    print(person)
    print("Ruta:", person.route)
    print()
    print("Mapa:")
    print(grid)


if __name__ == "__main__":
    main()