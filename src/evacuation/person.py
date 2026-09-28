class Person:
    def __init__(self, person_id, position, target_exit=None):
        self.person_id = person_id
        self.position = position
        self.target_exit = target_exit
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
            f"Salida objetivo: {self.target_exit} | "
            f"Evacuada: {self.evacuated}"
        )

def create_people(positions):
    people = []

    for person_id, position in enumerate(positions, start=1):
        people.append(
            Person(
                person_id=person_id,
                position=position
            )
        )

    return people