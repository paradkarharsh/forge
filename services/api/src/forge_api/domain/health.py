from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServiceHealth:
    service: str
    environment: str
    status: str
