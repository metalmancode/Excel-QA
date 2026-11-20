"""Domain errors mapped to predictable API responses."""


class InvalidWorkbook(ValueError):
    """The uploaded file cannot be accepted as a workbook."""

    pass


class InvalidPlan(ValueError):
    """The plan cannot be executed against the selected worksheet."""

    pass


class PlannerUnavailable(RuntimeError):
    """The planner cannot provide a usable structured response."""

    pass
