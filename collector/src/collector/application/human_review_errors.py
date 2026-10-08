class OperationalResolutionNotFoundError(ValueError):
    """The requested operational resolution does not exist."""

    def __init__(self, resolution_id: str):
        super().__init__(f"operational resolution not found: {resolution_id}")
