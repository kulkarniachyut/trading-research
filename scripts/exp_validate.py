"""OOS validation: take the configs that looked good on the 2023 in-sample year and measure them
on untouched years (2021/2022/2024). A real edge holds across regimes and varies *smoothly* with
the displacement threshold; a lucky fit spikes at one value and collapses around it.
"""

from __future__ import annotations

from scripts.exp_ict import _bars, run_config
from src.data.alpaca import AlpacaProvider

YEARS = ["2021", "2022", "2024"]  # 2023 was in-sample; these are holdout

# displacement-strength sweep (robustness) + the confirmation combo
CANDIDATES: dict[str, dict] = {
    "baseline(1.2)": {},
    "disp_1.5": {"displacement_atr_mult": 1.5},
    "disp_1.8": {"displacement_atr_mult": 1.8},
    "disp_2.0": {"displacement_atr_mult": 2.0},
    "disp_2.5": {"displacement_atr_mult": 2.5},
    "disp2.0+confirm": {"displacement_atr_mult": 2.0, "entry_confirm": True},
    "disp2.0+bias+confirm": {"displacement_atr_mult": 2.0, "entry_confirm": True,
                             "require_daily_bias": True},
}


def main() -> None:
    prov = AlpacaProvider()
    data = {yr: _bars(prov, "SPY", f"{yr}-01-01", f"{yr}-12-31") for yr in YEARS}
    print(f"\n=== SPY OOS validation (holdout years {', '.join(YEARS)}) ===")
    header = f"{'config':22s}" + "".join(f"{yr+' n/win%/net':>22}" for yr in YEARS) + f"{'TOTAL net':>11}{'exp/t':>8}"
    print(header)
    for name, params in CANDIDATES.items():
        cells = []
        tot_net = 0.0
        tot_n = 0
        for yr in YEARS:
            n, win, net, exp, r1 = run_config("SPY", data[yr], params)
            cells.append(f"{n:3d}/{win:4.0f}/{net:7.0f}")
            tot_net += net
            tot_n += n
        exp = tot_net / tot_n if tot_n else 0.0
        row = f"{name:22s}" + "".join(f"{c:>22}" for c in cells) + f"{tot_net:11.0f}{exp:8.1f}"
        print(row)


if __name__ == "__main__":
    main()
