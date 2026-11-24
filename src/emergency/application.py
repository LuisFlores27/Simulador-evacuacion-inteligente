from evacuation.person import create_people
from emergency.scenario import EXIT_IDS, FLOOR_HEIGHT


def apply_scenario(grid, scenario, start_positions):
    """Apply a validated scenario to a fresh logical grid."""
    if scenario.emergency_type != "salida_bloqueada":
        primary_hazard = (
            grid.set_fire
            if scenario.emergency_type in {"incendio", "combinada"}
            else grid.set_danger
        )
        for position in scenario.zone_positions():
            _apply_zone_hazard(grid, scenario, primary_hazard, position)

    for zone, floor in scenario.danger_zones:
        if (zone, floor) != (scenario.zone, scenario.floor):
            for position in scenario.positions_for_zone(zone, floor):
                _apply_zone_hazard(
                    grid,
                    scenario,
                    grid.set_danger,
                    position,
                    floor,
                )

    for zone, floor in scenario.fire_zones:
        for position in scenario.positions_for_zone(zone, floor):
            _apply_zone_hazard(
                grid,
                scenario,
                grid.set_fire,
                position,
                floor,
            )

    for exit_name in scenario.blocked_exits:
        x, y = EXIT_IDS[exit_name.casefold()]
        grid.block_exit((x, y + grid.exit_offset_y))

    positions = list(start_positions(scenario.people, grid))
    if len(positions) != scenario.people:
        raise ValueError(
            f"El mapa solo permite ubicar {len(positions)} personas."
        )

    people = create_people(positions)
    return people


def _apply_zone_hazard(grid, scenario, hazard_setter, position, floor=None):
    if grid.floor_offsets is not None:
        source_floor = floor or scenario.floor
        default_offset = FLOOR_HEIGHT if source_floor == 2 else 0
        target_offset = grid.floor_offsets[source_floor]
        position = (position[0], position[1] + target_offset - default_offset)
    node = grid.get_node(*position)
    if node is not None and node.walkable:
        hazard_setter(*position)
