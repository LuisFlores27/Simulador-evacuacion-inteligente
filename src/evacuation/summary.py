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

    def as_dict(self):
        return {
            "total_people": self.total_people,
            "people_with_route": self.total_people - self.people_without_route,
            "people_without_route": self.people_without_route,
            "people_evacuated": self.people_evacuated,
            "people_not_evacuated": self.people_not_evacuated,
            "elapsed_time": self.elapsed_time,
            "available_exits": self.available_exits,
            "blocked_exits": self.blocked_exits,
            "exit_usage": dict(self.exit_usage),
            "evacuation_finished": self.evacuation_finished,
            "all_evacuated": self.complete,
            "complete": self.complete,
        }
