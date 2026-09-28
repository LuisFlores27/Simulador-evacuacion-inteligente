from evacuation.node import Node


class Grid:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.nodes = []

        for y in range(height):
            row = []

            for x in range(width):
                row.append(Node(x, y))

            self.nodes.append(row)

    def get_node(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.nodes[y][x]

        return None

    def set_obstacle(self, x, y):
        node = self.get_node(x, y)

        if node:
            node.walkable = False

    def __str__(self):
        result = []

        for row in self.nodes:
            line = ""

            for node in row:
                line += "." if node.walkable else "#"

            result.append(line)

        return "\n".join(result)