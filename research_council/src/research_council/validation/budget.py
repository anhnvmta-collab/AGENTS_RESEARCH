from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import Field

from research_council.schemas.models import Schema


class LiveResearchBudget(Schema):
    max_total_cost: float = Field(default=5, ge=0)
    max_model_calls: int = Field(default=80, ge=0)
    max_search_calls: int = Field(default=1000, ge=0)
    max_core_papers: int = Field(default=12, ge=0)
    max_deep_reads: int = Field(default=12, ge=0)
    max_novelty_iterations: int = Field(default=3, ge=0, le=3)


class BudgetUsage(Schema):
    model_calls: int = Field(default=0, ge=0)
    search_calls: int = Field(default=0, ge=0)
    core_papers: int = Field(default=0, ge=0)
    deep_reads: int = Field(default=0, ge=0)
    novelty_iterations: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0, ge=0)
    reserved_cost: float = Field(default=0, ge=0)
    exhausted: bool = False
    reasons: list[str] = Field(default_factory=list)


class LiveBudgetExhausted(RuntimeError):
    pass


class BudgetLedger:
    """Synchronous admission inside one event loop; persist before every expensive action."""

    def __init__(
        self,
        budget: LiveResearchBudget,
        usage: BudgetUsage | None = None,
        persist: Callable[[BudgetUsage], None] | None = None,
    ) -> None:
        self.budget, self.usage, self.persist = budget, usage or BudgetUsage(), persist

    def save(self) -> None:
        if self.persist:
            self.persist(self.usage)

    def stop(self, reason: str) -> None:
        self.usage.exhausted = True
        if reason not in self.usage.reasons:
            self.usage.reasons.append(reason)
        self.save()
        raise LiveBudgetExhausted("BUDGET_EXHAUSTED: " + reason)

    def ensure_active(self) -> None:
        if self.usage.exhausted:
            raise LiveBudgetExhausted("BUDGET_EXHAUSTED: partial results retained")

    def consume(self, operation: Literal["search_calls", "deep_reads"]) -> None:
        self.ensure_active()
        if getattr(self.usage, operation) >= getattr(self.budget, "max_" + operation):
            self.stop(operation + " limit reached")
        setattr(self.usage, operation, getattr(self.usage, operation) + 1)
        self.save()

    def reserve_model(self, amount: float) -> None:
        self.ensure_active()
        if self.usage.model_calls >= self.budget.max_model_calls:
            self.stop("model call limit reached")
        if (
            self.usage.estimated_cost + self.usage.reserved_cost + amount
            > self.budget.max_total_cost
        ):
            self.stop("conservative model cost reservation exceeds limit")
        self.usage.model_calls += 1
        self.usage.reserved_cost += amount
        self.save()

    def settle_model(self, reservation: float, cost: float) -> None:
        self.usage.reserved_cost = max(0, self.usage.reserved_cost - reservation)
        self.usage.estimated_cost += cost
        if self.usage.estimated_cost + self.usage.reserved_cost > self.budget.max_total_cost:
            self.usage.exhausted = True
            self.usage.reasons.append(
                "Reported provider cost exceeded the reserved estimate; operator review required."
            )
        self.save()

    def begin_novelty(self, iteration: int) -> None:
        self.ensure_active()
        if iteration > self.budget.max_novelty_iterations:
            self.stop("novelty iteration limit reached")
        self.usage.novelty_iterations = max(self.usage.novelty_iterations, iteration)
        self.save()

    def select_core(self, count: int) -> None:
        if count > self.budget.max_core_papers:
            self.stop("CORE paper limit exceeded")
        self.usage.core_papers = count
        self.save()
