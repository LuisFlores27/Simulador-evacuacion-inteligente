class Node:
    def __init__(self, x, y, node_type="libre"):
        self.x = x
        self.y = y
        self.node_type = node_type

    @property
    def position(self):
        return (self.x, self.y)

    @property
    def walkable(self):
        return self.node_type != "obstaculo"

    def __str__(self):
        return (
            f"Nodo {self.position} | "
            f"Tipo: {self.node_type}"
        )