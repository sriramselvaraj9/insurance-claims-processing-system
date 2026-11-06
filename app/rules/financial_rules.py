"""Pure deterministic financial arithmetic and reserve/settlement calculation rules.

All calculations use fixed-point Decimal arithmetic with ROUND_HALF_UP rounding.
Floating-point arithmetic is strictly prohibited.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple

DEFAULT_EXPENSE_RATIO = Decimal("0.1200")
CENT = Decimal("0.01")


class SettlementBreakdown(NamedTuple):
    allowable_loss: Decimal
    deductible_applied: Decimal
    copay_applied: Decimal
    net_settlement_amount: Decimal


class ReserveBreakdown(NamedTuple):
    allowable_loss: Decimal
    indemnity_reserve: Decimal
    expense_reserve: Decimal
    total_reserve: Decimal


def quantize_money(amount: Decimal) -> Decimal:
    """Round a Decimal amount to standard 2-decimal currency precision."""
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def compute_allowable_loss(loss_amount: Decimal, coverage_limit: Decimal) -> Decimal:
    """Calculate the allowable loss capped at coverage limit (NEG-05)."""
    return quantize_money(min(max(loss_amount, Decimal("0.00")), coverage_limit))


def compute_indemnity_reserve(
    estimated_loss: Decimal,
    coverage_limit: Decimal,
    deductible: Decimal,
) -> Decimal:
    """Calculate indemnity reserve: max(0, min(loss, limit) - deductible)."""
    allowable = compute_allowable_loss(estimated_loss, coverage_limit)
    indemnity = max(Decimal("0.00"), allowable - deductible)
    return quantize_money(indemnity)


def compute_expense_reserve(
    indemnity_reserve: Decimal,
    expense_ratio: Decimal = DEFAULT_EXPENSE_RATIO,
) -> Decimal:
    """Calculate loss adjustment expense reserve: indemnity_reserve * expense_ratio."""
    expense = indemnity_reserve * expense_ratio
    return quantize_money(expense)


def compute_total_reserve(
    estimated_loss: Decimal,
    coverage_limit: Decimal,
    deductible: Decimal,
    expense_ratio: Decimal = DEFAULT_EXPENSE_RATIO,
) -> ReserveBreakdown:
    """Compute complete reserve breakdown (indemnity + expense)."""
    allowable = compute_allowable_loss(estimated_loss, coverage_limit)
    indemnity = compute_indemnity_reserve(estimated_loss, coverage_limit, deductible)
    expense = compute_expense_reserve(indemnity, expense_ratio)
    total = quantize_money(indemnity + expense)
    return ReserveBreakdown(
        allowable_loss=allowable,
        indemnity_reserve=indemnity,
        expense_reserve=expense,
        total_reserve=total,
    )


def compute_settlement(
    claimed_amount: Decimal,
    coverage_limit: Decimal,
    deductible: Decimal,
    copay_percentage: Decimal = Decimal("0.00"),
) -> SettlementBreakdown:
    """Compute deterministic net settlement applying limits, deductibles, and copays.

    Formula:
    1. Allowable Loss = min(Claimed Amount, Coverage Limit)
    2. Amount Subject to Copay = max(0, Allowable Loss - Deductible)
    3. Copay Reduction = Amount Subject to Copay * (Copay Percentage / 100)
    4. Net Settlement = max(0, Amount Subject to Copay - Copay Reduction)
    """
    allowable = compute_allowable_loss(claimed_amount, coverage_limit)
    base_after_deductible = max(Decimal("0.00"), allowable - deductible)
    deductible_applied = min(deductible, allowable)

    copay_rate = max(Decimal("0.00"), min(copay_percentage, Decimal("100.00"))) / Decimal("100.00")
    copay_reduction = quantize_money(base_after_deductible * copay_rate)

    net_settlement = max(Decimal("0.00"), base_after_deductible - copay_reduction)

    return SettlementBreakdown(
        allowable_loss=allowable,
        deductible_applied=quantize_money(deductible_applied),
        copay_applied=copay_reduction,
        net_settlement_amount=quantize_money(net_settlement),
    )
