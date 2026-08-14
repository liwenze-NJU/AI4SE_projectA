"""CompositeSensorRunner — runs an ordered list of SensorRunner instances.

The composite exposes the loop's sensor surface: composition wires the
configured, configuration-owned SensorRunner instances into one adapter so
the AgentLoop can call a single run_all() and collect all FeedbackResults.
"""

from codeguard.feedback import FeedbackResult
from codeguard.feedback.sensor import SensorRunner


class CompositeSensorRunner:
    """Runs each configured SensorRunner in registration order."""

    def __init__(self, runners: list[SensorRunner]):
        if not runners:
            raise ValueError("At least one sensor runner is required")
        self._runners = list(runners)

    def run_all(self) -> list[FeedbackResult]:
        return [runner.run() for runner in self._runners]
