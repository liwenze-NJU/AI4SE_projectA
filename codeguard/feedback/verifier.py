from codeguard.feedback import FeedbackResult


class ObjectiveVerifier:
    """Verifies that all required sensors have FINAL PASSED results.

    Per SPEC §3.5: COMPLETED is only reachable from FINAL_VALIDATION.
    INTERMEDIATE_VALIDATION PASSED cannot lead to COMPLETED.
    For duplicate sensor_ids, the last result (by list position) wins.
    """

    def __init__(self, required_sensors: list[str] | None = None):
        self._required = required_sensors or []

    def verify(self, results: list[FeedbackResult]) -> bool:
        if not self._required:
            return True

        # Build map of sensor_id -> last result (position-based)
        last_by_sensor: dict[str, FeedbackResult] = {}
        for r in results:
            last_by_sensor[r.sensor_id] = r

        for required in self._required:
            if required not in last_by_sensor:
                return False
            r = last_by_sensor[required]
            if r.status != "PASSED":
                return False
            if r.validation_type != "FINAL":
                return False

        return True