import random


class Person:
    def __init__(self, person_id, position, target_exit=None):
        self.person_id = person_id
        self.position = position
        self.target_exit = target_exit

        self.route = []
        self.route_index = 0

        self.evacuated = False

    def set_route(self, route):
        self.route = route
        self.route_index = 0

    def move_next(self):
        if self.evacuated:
            return

        if not self.route:
            return

        if self.route_index >= len(self.route) - 1:
            if self.position == self.target_exit:
                self.evacuated = True

            return

        self.route_index += 1
        self.position = self.route[self.route_index]

        if self.position == self.target_exit:
            self.evacuated = True

    def evacuate(self):
        self.evacuated = True

    def has_route(self):
        return bool(self.route)

    def get_current_position(self):
        return self.position

    def __str__(self):
        return (
            f"Persona {self.person_id} | "
            f"Posición: {self.position} | "
            f"Salida objetivo: {self.target_exit} | "
            f"Paso: {self.route_index}/{max(len(self.route) - 1, 0)} | "
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


def create_random_people(grid, amount):
    available_positions = []

    for y in range(grid.height):
        for x in range(grid.width):
            node = grid.get_node(x, y)

            if node and node.node_type == "libre":
                available_positions.append(node.position)

    amount = min(amount, len(available_positions))

    selected_positions = random.sample(
        available_positions,
        amount
    )

    return create_people(selected_positions)