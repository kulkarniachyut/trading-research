"""Carry paper-trading harness — SAFE (no real orders), honors 'paper trade until then'.

Operationalizes the parked funding-carry sleeve into a runnable daily paper tracker:
  - Reads live Binance basket funding (like carry_regime_monitor).
  - If the regime is DEPLOY (basket ann funding ≥ threshold): the delta-neutral target book is
    equal-weight across the 9 coins, total notional = equity × leverage (≤ user's 2-3x cap),
    long spot + short perp each. Logs the would-be positions.
  - Accrues PAPER carry = realized funding since the last run (net ≈ half gross, basis offset) on
    the held notional, and updates a paper-equity curve in data/crypto_paper_journal.jsonl.
  - If STAND ASIDE: logs flat (no positions) — the disciplined default in the current regime.

This places NO orders anywhere. It is the paper record that proves the edge live (or not) before
any real capital, and the template the real Binance executor (task #8) will mirror. Run it daily.

Usage: carry_paper.py [--equity 10000] [--leverage 2.5]
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASKET = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
          "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]
JOURNAL = Path("data/crypto_paper_journal.jsonl")
DEPLOY_ANN = 0.10
NET_FRACTION = 0.5   # net carry ≈ half gross funding (basis offset, rigor pass)


def _opt_f(flag: str, default: float) -> float:
    a = sys.argv[1:]
    return float(a[a.index(flag) + 1]) if flag in a else default


def _live_funding() -> dict[str, float]:
    url = "https://fapi.binance.com/fapi/v1/premiumIndex"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = {x["symbol"]: x for x in json.loads(r.read())}
    return {s: float(data[s]["lastFundingRate"]) for s in BASKET if s in data}


def _last_entry() -> dict | None:
    if not JOURNAL.exists():
        return None
    lines = [ln for ln in JOURNAL.read_text().splitlines() if ln.strip()]
    return json.loads(lines[-1]) if lines else None


def main() -> None:
    equity = _opt_f("--equity", 10_000.0)
    leverage = min(_opt_f("--leverage", 2.5), 3.0)  # hard-cap 3x per user mandate
    fund = _live_funding()
    if not fund:
        raise SystemExit("no funding data")

    per8h = {s: r for s, r in fund.items()}
    basket_ann = sum(v * 3 * 365 for v in per8h.values()) / len(per8h)
    deploy = basket_ann >= DEPLOY_ANN

    prev = _last_entry()
    paper_equity = prev["paper_equity"] if prev else equity
    # accrue carry earned since last run IF we were deployed last time (one 8h funding ≈ snapshot)
    accrued = 0.0
    if prev and prev.get("deployed"):
        # net carry on prior notional over ~the elapsed period; approximate with prior basket funding
        prior_notional = prev["notional"]
        # one funding interval's net carry as a conservative per-run accrual
        accrued = prior_notional * prev["basket_per8h"] * NET_FRACTION
        paper_equity += accrued

    notional = equity * leverage if deploy else 0.0
    per_coin = notional / len(BASKET) if deploy else 0.0
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "regime": "DEPLOY" if deploy else "STAND_ASIDE",
        "deployed": deploy,
        "basket_ann_funding": round(basket_ann, 4),
        "basket_per8h": round(sum(per8h.values()) / len(per8h), 6),
        "equity": equity,
        "leverage": leverage,
        "notional": round(notional, 2),
        "per_coin_notional": round(per_coin, 2),
        "accrued_since_last": round(accrued, 2),
        "paper_equity": round(paper_equity, 2),
        "positions": ({s: {"long_spot": round(per_coin, 2), "short_perp": round(per_coin, 2)}
                       for s in BASKET} if deploy else {}),
    }
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a") as f:
        f.write(json.dumps(entry) + "\n")

    print("=== CARRY PAPER (safe, no real orders) ===")
    print(f"  regime: {entry['regime']}  | basket ann funding {basket_ann*100:+.1f}% "
          f"(deploy ≥ {DEPLOY_ANN*100:.0f}%)")
    print(f"  equity ${equity:,.0f}  leverage {leverage}x  -> target notional ${notional:,.0f} "
          f"(${per_coin:,.0f}/coin delta-neutral)")
    if accrued:
        print(f"  accrued paper carry since last run: ${accrued:+,.2f}")
    print(f"  paper equity: ${paper_equity:,.2f}")
    if not deploy:
        print("  -> STAND ASIDE (regime dead). No paper positions. Re-run daily; deploys when funding fattens.")
    else:
        print("  -> DEPLOY: open equal-weight delta-neutral (long spot + short perp) per coin; "
              "flatten any coin whose rolling-7d funding < 0; swift exit on basis/liquidation stress.")
    print(f"  journal: {JOURNAL}")


if __name__ == "__main__":
    main()
