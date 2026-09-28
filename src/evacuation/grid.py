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

    def set_node_type(self, x, y, node_type):
        node = self.get_node(x, y)

        if node:
            node.node_type = node_type

    def set_obstacle(self, x, y):
        self.set_node_type(x, y, "obstaculo")

    def set_danger(self, x, y):
        self.set_node_type(x, y, "peligro")

    def set_exit(self, x, y):
        self.set_node_type(x, y, "salida")

    def get_exits(self):
        exits = []

        for row in self.nodes:
            for node in row:
                if node.node_type == "salida":
                    exits.append(node.position)

        return exits

    def block_exit(self, position):
        self.set_node_type(
            position[0],
            position[1],
            "obstaculo"
        )

    def __str__(self):
        symbols = {
            "libre": ".",
            "obstaculo": "#",
            "peligro": "!",
            "salida": "E"
        }

        result = []

        for row in self.nodes:
            line = ""

            for node in row:
                line += symbols.get(node.node_type, "?")

            result.append(line)

        return "\n".join(result)