from evacuation.person import create_people
from emergency.scenario import EXIT_IDS


def apply_scenario(grid, scenario, start_positions):
    """Apply a validated scenario to a fresh logical grid."""
    if scenario.emergency_type != "salida_bloqueada":
        hazard_setter = (
            grid.set_fire
            if scenario.emergency_type in {"incendio", "combinada"}
            else grid.set_danger
        )
        for position in scenario.zone_positions():
            node = grid.get_node(*position)
            if node is not None and node.walkable:
                hazard_setter(*position)

    for exit_name in scenario.blocked_exits:
        grid.block_exit(EXIT_IDS[exit_name.casefold()])

    positions = list(start_positions(scenario.people, grid))
    if len(positions) != scenario.people:
        raise ValueError(
            f"El mapa solo permite ubicar {len(positions)} personas."
        )

    people = create_people(positions)
    return people
