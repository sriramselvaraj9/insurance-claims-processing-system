"""Common base dataclasses and types for the business rules engine."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    name: str
    passed: bool
    reason: str
    entity_id: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "passed": self.passed,
            "reason": self.reason,
            "entity_id": self.entity_id,
            "metadata": self.metadata or {},
        }
