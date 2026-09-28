import heapq
import math


class AStar:
    def __init__(self, grid):
        self.grid = grid

    def heuristic(self, current, goal):
        return math.sqrt(
            (current.x - goal.x) ** 2 +
            (current.y - goal.y) ** 2
        )

    def get_neighbors(self, node):
        directions = [
            (0, -1),
            (0, 1),
            (-1, 0),
            (1, 0)
        ]

        neighbors = []

        for dx, dy in directions:
            neighbor = self.grid.get_node(
                node.x + dx,
                node.y + dy
            )

            if neighbor and neighbor.walkable:
                neighbors.append(neighbor)

        return neighbors

    def get_movement_cost(self, node):
        if node.node_type == "peligro":
            return 5

        return 1

    def find_path(self, start_position, goal_position):
        start = self.grid.get_node(
            start_position[0],
            start_position[1]
        )

        goal = self.grid.get_node(
            goal_position[0],
            goal_position[1]
        )

        if start is None or goal is None:
            return []

        if not start.walkable or not goal.walkable:
            return []

        open_set = []

        heapq.heappush(
            open_set,
            (0, start.position)
        )

        came_from = {}

        cost_so_far = {
            start.position: 0
        }

        while open_set:
            _, current_position = heapq.heappop(open_set)

            current = self.grid.get_node(
                current_position[0],
                current_position[1]
            )

            if current.position == goal.position:
                return self.reconstruct_path(
                    came_from,
                    current.position
                )

            for neighbor in self.get_neighbors(current):
                movement_cost = self.get_movement_cost(neighbor)

                new_cost = (
                    cost_so_far[current.position]
                    + movement_cost
                )

                if (
                    neighbor.position not in cost_so_far
                    or new_cost < cost_so_far[neighbor.position]
                ):
                    cost_so_far[neighbor.position] = new_cost

                    priority = (
                        new_cost
                        + self.heuristic(neighbor, goal)
                    )

                    heapq.heappush(
                        open_set,
                        (priority, neighbor.position)
                    )

                    came_from[neighbor.position] = current.position

        return []

    def find_best_exit(self, start_position, exits):
        best_path = []
        best_cost = float("inf")
        best_exit = None

        for exit_position in exits:
            path = self.find_path(
                start_position,
                exit_position
            )

            if not path:
                continue

            cost = self.calculate_path_cost(path)

            if cost < best_cost:
                best_cost = cost
                best_path = path
                best_exit = exit_position

        return best_exit, best_path, best_cost


    def calculate_path_cost(self, path):
        total_cost = 0

        for position in path[1:]:
            node = self.grid.get_node(
                position[0],
                position[1]
            )

            total_cost += self.get_movement_cost(node)

        return total_cost

    def reconstruct_path(self, came_from, current):
        path = [current]

        while current in came_from:
            current = came_from[current]
            path.append(current)

        path.reverse()

        return path