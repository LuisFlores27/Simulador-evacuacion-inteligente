from collections import Counter

from evacuation.astar import AStar
from evacuation.summary import EvacuationSummary


class EvacuationManager:
    def __init__(self, grid, people):
        self.grid = grid
        self.people = people
        self.astar = AStar(grid)
        self.elapsed_time = 0.0

    def calculate_routes(self):
        exits = self.grid.get_exits()

        for person in self.people:
            if person.evacuated:
                continue
            stair_route = getattr(self.grid, "stair_route", None)
            if (
                stair_route
                and person.position[1] < self.grid.floor_offsets[1]
            ):
                route_to_stairs = self.astar.find_path(
                    person.position,
                    stair_route[0],
                )
                stair_landing = getattr(
                    self.grid,
                    "stair_exit_landing",
                    stair_route[-1],
                )
                route_to_landing = self.astar.find_path(
                    stair_route[-1],
                    stair_landing,
                )
                best_exit, route_from_landing, _ = (
                    self.astar.find_best_exit(stair_landing, exits)
                )
                if (
                    route_to_stairs
                    and route_to_landing
                    and route_from_landing
                ):
                    route = (
                        route_to_stairs
                        + stair_route[1:]
                        + route_to_landing[1:]
                        + route_from_landing[1:]
                    )
                else:
                    route = []
            else:
                blocked_stairs = None
                floor_offsets = getattr(self.grid, "floor_offsets", None)
                if stair_route and floor_offsets and (
                    person.position[1] >= floor_offsets[1]
                ):
                    blocked_stairs = {
                        position
                        for position in stair_route
                        if position[1] >= floor_offsets[1]
                    }
                best_exit, route, _ = self.astar.find_best_exit(
                    person.position,
                    exits,
                    blocked_positions=blocked_stairs,
                )
            person.target_exit = best_exit
            person.set_route(route)
            if best_exit == person.position:
                person.evacuate()

    def move_people(self):
        for person in self.people:
            person.move_next()

    def all_evacuated(self):
        return bool(self.people) and all(
            person.evacuated
            for person in self.people
        )

    def is_finished(self):
        return all(
            person.evacuated or not person.has_route()
            for person in self.people
        )

    def get_evacuated_count(self):
        return sum(person.evacuated for person in self.people)

    def get_people_without_route(self):
        return sum(
            not person.evacuated and not person.has_route()
            for person in self.people
        )

    def get_exit_usage(self):
        usage = Counter(
            person.used_exit
            for person in self.people
            if person.evacuated and person.used_exit is not None
        )
        return {
            position: usage[position]
            for position in self.grid.exits
        }

    def get_evacuation_summary(self):
        total_people = len(self.people)
        people_evacuated = self.get_evacuated_count()
        return EvacuationSummary(
            total_people=total_people,
            people_evacuated=people_evacuated,
            people_not_evacuated=total_people - people_evacuated,
            people_without_route=self.get_people_without_route(),
            elapsed_time=self.elapsed_time,
            available_exits=len(self.grid.get_exits()),
            blocked_exits=len(self.grid.blocked_exits),
            exit_usage=self.get_exit_usage(),
            evacuation_finished=self.is_finished(),
            complete=bool(self.people) and self.all_evacuated(),
        )
