class Person:
    def __init__(self, person_id, position):
        self.person_id = person_id
        self.position = position
        self.route = []
        self.evacuated = False

    def set_route(self, route):
        self.route = route

    def evacuate(self):
        self.evacuated = True

    def __str__(self):
        return (
            f"Persona {self.person_id} | "
            f"Posición: {self.position} | "
            f"Evacuada: {self.evacuated}"
        )