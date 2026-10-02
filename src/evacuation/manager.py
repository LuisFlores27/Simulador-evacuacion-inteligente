from evacuation.astar import AStar


class EvacuationManager:
    def __init__(self, grid, people):
        self.grid = grid
        self.people = people
        self.astar = AStar(grid)

    def calculate_routes(self):
        exits = self.grid.get_exits()

        for person in self.people:
            best_exit, route, cost = self.astar.find_best_exit(
                person.position,
                exits
            )

            person.target_exit = best_exit
            person.set_route(route)

    def move_people(self):
        for person in self.people:
            person.move_next()

    def all_evacuated(self):
        if not self.people:
            return False

        return all(
            person.evacuated
            for person in self.people
        )

    def get_evacuated_count(self):
        return sum(
            1
            for person in self.people
            if person.evacuated
        )

    def get_evacuation_summary(self):
        total_people = len(self.people)

        people_with_route = sum(
            1
            for person in self.people
            if person.has_route()
        )

        people_evacuated = self.get_evacuated_count()

        return {
            "total_people": total_people,
            "people_with_route": people_with_route,
            "people_evacuated": people_evacuated,
            "all_evacuated": self.all_evacuated()
        }