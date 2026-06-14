"""Step 6 risk layer — combine the strategy sleeves into ONE risk-sized, capped book.

The research produced three sleeves (mean-reversion core, VIX-carry, trend hedge); each emits its
own desired positions. This allocator is the single place that turns those into the actual orders,
enforcing the CLAUDE.md risk rules in one spot:
  - **sleeve weights**: allocate the book by intended risk share (e.g. 50/30/20), not by whoever
    signals loudest;
  - **max gross leverage**: total |notional| / equity is hard-capped (scaled down pro-rata if the
    summed sleeves would breach it);
  - **drawdown circuit breaker**: at/under a peak-to-trough threshold the book is forced flat.

Pure and deterministic so it is fully unit-testable without a broker; the paper/live loop calls
``allocate`` and submits the resulting targets. No look-ahead, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SleeveTarget:
    """One sleeve's desired book: symbol -> signed target notional ($, +long / -short)."""

    name: str
    targets: dict[str, float] = field(default_factory=dict)

    @property
    def gross(self) -> float:
        return sum(abs(v) for v in self.targets.values())


@dataclass(frozen=True, slots=True)
class AllocationResult:
    targets: dict[str, float]              # final symbol -> signed target notional ($)
    sleeve_gross: dict[str, float]         # gross $ actually allocated per sleeve (post-scaling)
    gross_leverage: float                  # final total gross / equity
    scaled: float                          # scale factor applied (1.0 = no cap hit)
    halted: bool                           # drawdown circuit breaker tripped -> all flat


def allocate(
    sleeves: list[SleeveTarget],
    weights: dict[str, float],
    equity: float,
    *,
    max_gross_leverage: float = 1.0,
    current_drawdown: float = 0.0,
    drawdown_halt: float = 0.5,
) -> AllocationResult:
    """Blend sleeve books by ``weights`` (risk share), cap total gross leverage, and honor the
    drawdown circuit breaker.

    Each sleeve's own targets are scaled so that sleeve's gross equals ``weight * equity *
    max_gross_leverage`` (its risk budget), preserving the sleeve's internal proportions. If the
    summed gross still exceeds ``max_gross_leverage * equity`` (it shouldn't, given weights sum to
    ≤1, but guards against weights > 1), everything is scaled down pro-rata. At/over the drawdown
    halt the whole book goes flat.
    """
    if equity <= 0:
        raise ValueError("equity must be positive")
    if current_drawdown >= drawdown_halt:
        return AllocationResult({}, {}, 0.0, 0.0, halted=True)

    budget = equity * max_gross_leverage
    blended: dict[str, float] = {}
    sleeve_gross: dict[str, float] = {}
    for s in sleeves:
        w = weights.get(s.name, 0.0)
        if w <= 0 or s.gross <= 0:
            sleeve_gross[s.name] = 0.0
            continue
        # scale this sleeve so its gross == w * budget (its risk slice), keeping internal weights
        k = (w * budget) / s.gross
        sleeve_gross[s.name] = w * budget
        for sym, v in s.targets.items():
            blended[sym] = blended.get(sym, 0.0) + v * k

    total_gross = sum(abs(v) for v in blended.values())
    scale = 1.0
    if total_gross > budget and total_gross > 0:
        scale = budget / total_gross
        blended = {k: v * scale for k, v in blended.items()}
        sleeve_gross = {k: v * scale for k, v in sleeve_gross.items()}
        total_gross = budget

    return AllocationResult(
        targets={k: v for k, v in blended.items() if abs(v) > 1e-9},
        sleeve_gross=sleeve_gross,
        gross_leverage=total_gross / equity if equity else 0.0,
        scaled=scale,
        halted=False,
    )
