"""Carry regime monitor — the 'deploy carry now?' alarm (go-wide backlog #1).

Funding carry is PARKED because mid-2026 is a low-carry regime (OOS net +0.8% vs IS +7.4%).
This monitor reads the CURRENT funding regime live and fires a deploy/stand-aside signal, so the
parked edge gets picked up at the right time (high funding) instead of forced in a dead regime —
the discipline a prior-losses trader needs.

Reads Binance live funding (premium index / lastFundingRate) for the 9-coin basket, annualizes the
current basket funding, and compares to thresholds derived from the backtest:
  - IS era basket funding ~ +12-16%/yr (carry net ~+7%); OOS 2025/26 ~ +0.6-2%/yr (carry net ~+0.8%).
  - DEPLOY when annualized basket funding ≥ ~10% (carry net ~half ≈ 5%+ → worth 2-3x).
  - STAND ASIDE below ~6%. Between = watch.
Net carry ≈ ~half the gross funding (basis offset, from the rigor pass) minus fees.

Usage: carry_regime_monitor.py   (no args; live read)
"""

from __future__ import annotations

import json
import urllib.request

BASKET = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
          "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT"]
DEPLOY_ANN = 0.10   # annualized basket funding to justify deploying carry at 2-3x
WATCH_ANN = 0.06
NET_FRACTION = 0.5  # net carry ≈ half the gross funding sum (basis convergence, rigor pass)


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def main() -> None:
    # one call returns premiumIndex (incl lastFundingRate) for all symbols
    data = {x["symbol"]: x for x in _get("https://fapi.binance.com/fapi/v1/premiumIndex")}
    print("=== CARRY REGIME MONITOR (live Binance funding) ===")
    print(f"  deploy if basket ann funding ≥ {DEPLOY_ANN*100:.0f}%  |  net carry ≈ "
          f"{NET_FRACTION*100:.0f}% of gross (basis offset)\n")
    rates = []
    for sym in BASKET:
        d = data.get(sym)
        if not d:
            print(f"  {sym}: n/a")
            continue
        last = float(d["lastFundingRate"])         # per 8h
        ann = last * 3 * 365
        rates.append(ann)
        print(f"  {sym:9s} last funding/8h {last*100:+.4f}%  -> ann {ann*100:+6.1f}%")
    if not rates:
        raise SystemExit("no funding data")
    basket_ann = sum(rates) / len(rates)
    net_est = basket_ann * NET_FRACTION
    signal = ("DEPLOY" if basket_ann >= DEPLOY_ANN
              else "WATCH" if basket_ann >= WATCH_ANN else "STAND ASIDE")
    print(f"\n  BASKET ann funding {basket_ann*100:+.1f}%  -> est net carry {net_est*100:+.1f}% "
          f"unlevered ({net_est*2.5*100:+.1f}% at 2.5x)")
    print(f"  >>> SIGNAL: {signal}  <<<")
    if signal != "DEPLOY":
        print("  Carry stays PARKED. Re-run this monitor periodically; deploy only when it flips to DEPLOY.")
    else:
        print("  Regime is fat — carry worth deploying at 2-3x cross-margin (flatten-when-funding<0, swift exits).")


if __name__ == "__main__":
    main()
