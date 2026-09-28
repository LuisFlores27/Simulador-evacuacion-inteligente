from emergency.scenario import EmergencyScenario
from evacuation.person import Person


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

    print("Simulador de Evacuación Inteligente")
    print("-----------------------------------")
    print(scenario)
    print()
    print(person)
    print("Ruta:", person.route)


if __name__ == "__main__":
    main()