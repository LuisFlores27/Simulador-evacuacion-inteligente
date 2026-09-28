class Node:
    def __init__(self, x, y, walkable=True):
        self.x = x
        self.y = y
        self.walkable = walkable

    @property
    def position(self):
        return (self.x, self.y)

    def __str__(self):
        estado = "libre" if self.walkable else "bloqueado"
        return f"Nodo {self.position} | {estado}"