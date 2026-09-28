class EmergencyScenario:
    def __init__(
        self,
        emergency_type,
        zone,
        people,
        blocked_exit=None
    ):
        self.emergency_type = emergency_type
        self.zone = zone
        self.people = people
        self.blocked_exit = blocked_exit

    def __str__(self):
        return (
            f"Emergencia: {self.emergency_type}\n"
            f"Zona afectada: {self.zone}\n"
            f"Personas: {self.people}\n"
            f"Salida bloqueada: {self.blocked_exit}"
        )