"""Paper-experiment judge — compares the live journal against the PRE-REGISTERED gates.

Thresholds live in docs/STEP4_EDGE_SEARCH_PLAN.md ("Live paper experiment") and were fixed
before any live fill existed; this script only *reports* against them. Run any time:

    uv run python scripts/paper_review.py

It replays ``data/paper_journal.jsonl`` into per-system stats (signals, fills, expiries,
closed round-trips with realized R) and prints gate status. R per trade uses the journaled
stop distance (risk_cash at submission) — the same R-unit the backtest reports.
"""

from __future__ import annotations

import json
from collections import defaultdict

from src.core.config import REPO_ROOT

JOURNAL = REPO_ROOT / "data" / "paper_journal.jsonl"

# Pre-registered gates (see plan doc — do not edit after live data exists).
IBS_GATES = {"interim_n": 60, "full_n": 120, "fill_rate_min": 0.70,
             "exp_floor_at_full": -0.04, "backtest_exp": 0.026}
TOM_GATES = {"interim_n": 6, "full_n": 12, "backtest_exp": 0.057}


def main() -> None:
    if not JOURNAL.exists():
        print(f"no journal yet at {JOURNAL}")
        return
    recs = [json.loads(line) for line in JOURNAL.read_text().splitlines() if line.strip()]

    pend = sum(1 for r in recs if r.get("kind") == "pending_entry")
    expired = sum(1 for r in recs if r.get("kind") == "pending_expired")
    opens = [r for r in recs if r.get("kind") == "lot_open"]
    closes = [r for r in recs if r.get("kind") == "lot_close"]
    errors = [r for r in recs if r.get("kind") == "submit_error"]

    by_sys_open: dict[str, list[dict]] = defaultdict(list)
    for r in opens:
        by_sys_open[r.get("system", "?")].append(r)

    print(f"=== paper journal review — {len(recs)} records ===")
    print(f"  limit entries submitted: {pend}   expired unfilled: {expired}   "
          f"lots opened: {len(opens)}   lots closed: {len(closes)}   "
          f"submit errors: {len(errors)}")
    resolved = expired + len([r for r in opens if r.get("system") == "ibs"])
    if resolved:
        fr = len(by_sys_open["ibs"]) / resolved
        gate = "OK" if fr >= IBS_GATES["fill_rate_min"] else "BELOW PRE-REGISTERED 70% — FAIL"
        print(f"  IBS fill rate: {fr * 100:.0f}% of resolved signals "
              f"(backtest 81-94%)  [{gate}]")

    n_ibs = len([r for r in closes if r.get("system") == "ibs"])
    n_tom = len([r for r in closes if r.get("system") == "tom"])
    print(f"  closed round-trips: IBS {n_ibs}/{IBS_GATES['full_n']} toward full gate "
          f"(interim at {IBS_GATES['interim_n']}); TOM {n_tom}/{TOM_GATES['full_n']}")
    print("  NOTE: realized P&L per round-trip requires fill prices — extend the loop to")
    print("  record fill prices via broker order lookups once fills exist (first review).")
    if n_ibs >= IBS_GATES["interim_n"]:
        print("  >>> INTERIM GATE REACHED — compute realized expectancy vs pre-registered "
              f"floor ({IBS_GATES['exp_floor_at_full']:+.3f}R at n={IBS_GATES['full_n']}).")


if __name__ == "__main__":
    main()
