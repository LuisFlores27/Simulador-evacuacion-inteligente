from evacuation.node import Node


class Grid:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.nodes = []
        self.exits = {}
        self.blocked_exits = set()

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

    def set_exit(self, x, y):
        self.set_node_type(x, y, "salida")
        self.exits[(x, y)] = None

    def register_exit(self, position, identifier):
        self.exits[position] = identifier
        if position not in self.blocked_exits:
            self.set_node_type(*position, "salida")

    def get_exits(self):
        return [
            position
            for position in self.exits
            if position not in self.blocked_exits
        ]

    def block_exit(self, position):
        if position not in self.exits:
            raise ValueError(f"No existe una salida en {position}.")
        self.blocked_exits.add(position)
        self.set_node_type(*position, "salida_bloqueada")

    def unblock_exit(self, position):
        if position not in self.exits:
            raise ValueError(f"No existe una salida en {position}.")
        self.blocked_exits.discard(position)
        self.set_node_type(*position, "salida")

    def get_exit_identifier(self, position):
        return self.exits.get(position)

    def set_danger(self, x, y):
        node = self.get_node(x, y)
        if node is not None and node.node_type not in {
            "obstaculo",
            "salida",
            "salida_bloqueada",
        }:
            node.node_type = "peligro"

    def set_fire(self, x, y):
        node = self.get_node(x, y)
        if node is not None and node.node_type not in {
            "obstaculo",
            "salida",
            "salida_bloqueada",
        }:
            node.node_type = "incendio"

    def __str__(self):
        symbols = {
            "libre": ".",
            "obstaculo": "#",
            "peligro": "!",
            "incendio": "F",
            "salida": "E",
            "salida_bloqueada": "X",
        }

        result = []

        for row in self.nodes:
            line = ""

            for node in row:
                line += symbols.get(node.node_type, "?")

            result.append(line)

        return "\n".join(result)