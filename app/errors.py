"""Domain errors mapped to predictable API responses."""


class InvalidWorkbook(ValueError):
    pass


class InvalidPlan(ValueError):
    pass


class PlannerUnavailable(RuntimeError):
    pass
