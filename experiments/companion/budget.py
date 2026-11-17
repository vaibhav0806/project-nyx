"""Measured, capped OpenRouter experiments; never a production inference adapter."""

from experiments.companion.embedding_replay import budget_snapshot, check_budget
from nyx.cloud import CloudError, OpenRouter


class BudgetedClient(OpenRouter):
    def __init__(self, max_spend, *, max_requests=60):
        if type(max_requests) is not int or not 1 <= max_requests <= 96:
            raise ValueError("Evaluation request allowance must be 1–96")
        super().__init__()
        self.initial = budget_snapshot(self)
        self.max_spend = max_spend
        self.requests = 0
        self.max_requests = max_requests
        check_budget(self.initial, self.initial["usage"], max_spend)

    def request(self, *args, **kwargs):
        if self.requests >= self.max_requests:
            raise CloudError("Evaluation request limit reached")
        try:
            check_budget(
                budget_snapshot(self),
                self.initial["usage"],
                self.max_spend,
                reported_cost=sum(row.get("cost") or 0 for row in self.usage),
            )
        except ValueError as error:
            raise CloudError(str(error)) from None
        self.requests += 1
        return super().request(*args, **kwargs)
