from dataclasses import dataclass, field


@dataclass
class LoopState:
    run_id: int
    invalid_calls: int = 0
    fingerprints_seen: set[str] = field(default_factory=set)
    started_monotonic: float = 0.0
