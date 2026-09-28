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

    def get_evacuation_summary(self):
        total_people = len(self.people)
        people_with_route = 0

        for person in self.people:
            if person.route:
                people_with_route += 1

        return {
            "total_people": total_people,
            "people_with_route": people_with_route
        }