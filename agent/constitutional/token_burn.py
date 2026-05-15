"""Token burn guard — caps token usage per agent run.

Prevents runaway loops from burning budget silently.
Treated as a constitutional violation: exceeding the budget halts the run.
"""

from dataclasses import dataclass, field
from typing import Optional

from agent.constitutional.hard_limits import ConstitutionalViolation

# Default per-run budget. Override via TokenBurnGuard(budget=N).
DEFAULT_TOKEN_BUDGET = 50_000


@dataclass
class TokenBurnGuard:
    """Tracks token usage for a single agent run and enforces a hard budget.

    Usage:
        guard = TokenBurnGuard()
        guard.start_run("run-123")
        violation = guard.record(prompt_tokens=200, completion_tokens=150)
        if violation:
            halt_agent(violation)
    """

    budget: int = DEFAULT_TOKEN_BUDGET
    _run_id: str = field(default="", init=False, repr=False)
    _total_prompt: int = field(default=0, init=False, repr=False)
    _total_completion: int = field(default=0, init=False, repr=False)

    def start_run(self, agent_run_id: str) -> None:
        self._run_id = agent_run_id
        self._total_prompt = 0
        self._total_completion = 0

    def record(
        self, prompt_tokens: int, completion_tokens: int
    ) -> Optional[ConstitutionalViolation]:
        """Add tokens and return a violation if the budget is exceeded."""
        self._total_prompt += max(0, prompt_tokens)
        self._total_completion += max(0, completion_tokens)
        total = self._total_prompt + self._total_completion

        if total > self.budget:
            return ConstitutionalViolation(
                rule="TOKEN_BUDGET_EXCEEDED",
                reason=(
                    f"Run {self._run_id!r} used {total} tokens "
                    f"(budget={self.budget}). "
                    f"prompt={self._total_prompt}, "
                    f"completion={self._total_completion}"
                ),
                tool_name="<runtime>",
                inputs={"total_tokens": total, "budget": self.budget},
            )
        return None

    @property
    def tokens_used(self) -> int:
        return self._total_prompt + self._total_completion

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.budget - self.tokens_used)
