from emergency.scenario import EmergencyScenario


def main():
    scenario = EmergencyScenario(
        emergency_type="incendio",
        zone="laboratorio",
        people=30,
        blocked_exit="norte"
    )

    print("Simulador de Evacuación Inteligente")
    print("-----------------------------------")
    print(scenario)


if __name__ == "__main__":
    main()