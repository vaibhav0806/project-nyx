"""Measured, capped OpenRouter experiments; never a production inference adapter."""

from experiments.companion.embedding_replay import budget_snapshot, check_budget
from nyx.cloud import CloudError, OpenRouter


class BudgetedClient(OpenRouter):
    def __init__(self, max_spend, *, max_requests=60):
        if type(max_requests) is not int or not 1 <= max_requests <= 96:
            raise ValueError("Evaluation request allowance must be 1–96")
        super().__init__()
        self.initial = budget_snapshot(self)
        self.high_water_usage = self.initial["usage"]
        self.max_spend = max_spend
        self.requests = 0
        self.max_requests = max_requests
        check_budget(self.initial, self.initial["usage"], max_spend)

    def before_request(self):
        """Use the same guard for HTTP and the separately evaluated SDK stream."""
        if self.requests >= self.max_requests:
            raise CloudError("Evaluation request limit reached")
        try:
            snapshot = budget_snapshot(self)
            reported = sum(row.get("cost") or 0 for row in self.usage)
            check_budget(snapshot, self.initial["usage"], self.max_spend, reported_cost=reported)
            self.high_water_usage = max(self.high_water_usage, snapshot["usage"])
            check_budget(
                {**snapshot, "usage": self.high_water_usage},
                self.initial["usage"],
                self.max_spend,
                reported_cost=reported,
            )
        except ValueError as error:
            raise CloudError(str(error)) from None
        self.requests += 1

    def request(self, *args, **kwargs):
        self.before_request()
        return super().request(*args, **kwargs)
