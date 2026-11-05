from dataclasses import dataclass


@dataclass(frozen=True)
class EvacuationSummary:
    total_people: int
    people_evacuated: int
    people_not_evacuated: int
    people_without_route: int
    elapsed_time: float
    available_exits: int
    blocked_exits: int
    exit_usage: dict
    evacuation_finished: bool
    complete: bool
