"""Domain exceptions for lifecycle workflows."""


class InvalidStateTransitionError(Exception):
    """Raised when an illegal lifecycle transition is attempted."""

    def __init__(
        self,
        current_status: str,
        target_status: str,
        entity_name: str = "Claim",
        reason: str | None = None,
    ) -> None:
        message = (
            f"Cannot transition {entity_name} from '{current_status}' to '{target_status}'"
        )
        if reason:
            message += f": {reason}"
        super().__init__(message)
        self.current_status = current_status
        self.target_status = target_status
        self.entity_name = entity_name
        self.reason = reason

