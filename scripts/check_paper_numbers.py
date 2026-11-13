"""Check that every number quoted in paper/paper.tex matches results/."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
TEX = " ".join((ROOT / "paper" / "paper.tex").read_text().split())

res = pd.read_csv(R / "main_results.csv").set_index(["penetration", "mechanism"])
share = pd.read_csv(R / "smart_share_sweep.csv").set_index(["smart_share", "mechanism"])
pen = pd.read_csv(R / "penetration_sweep.csv").set_index(["penetration", "mechanism"])
pvq = pd.read_csv(R / "remedy_settings.csv")
fp = pd.read_csv(R / "fixed_point_history.csv")
P_MAX = 100.9
ex = pd.read_csv(R / "example_day_ev_p80.csv")  # Fig. 1
sch = pd.read_csv(R / "scheduler_sensitivity.csv")
sch = sch[sch.penetration == 100].pivot_table(index="mechanism", columns="scheduler",
                                              values=["p_overload_pct", "max_switch_on_chargers"])
ovl = sch["p_overload_pct"]
sync = sch["max_switch_on_chargers"]
SHARED = ["Static ToU", "Agile", "Network, no CPP", "Network + CPP"]


def m(p, name, col):
    return res.loc[(p, name), col]


def last10(case, s, pen_=None, mech="Network + CPP"):
    d = fp[(fp.case == case) & (fp.mechanism == mech) & (fp.smart_share == s)]
    if pen_ is not None:
        d = d[d.penetration == pen_]
    return d.sort_values("round").tail(10)[["slots_changed", "max_change_kw"]].mean()


dither = pvq[(pvq.instrument == "price") & (pvq.penetration == 100)].set_index("setting")
hyb = pvq[(pvq.mechanism == "Quota + price (hybrid)") & (pvq.penetration == 100)].set_index("setting")

CHECKS = [
    ("on 40.1--42.4\\% of days",
     f"{ovl.loc[SHARED, 'latest'].min():.1f}-{ovl.loc[SHARED, 'latest'].max():.1f}"),
    ("against\n37.8\\% for uncontrolled", f"{ovl.loc['Uncontrolled', 'none']:.1f}"),
    ("from 3.5 to\n8.9", f"{sync.loc['Network, no CPP', 'latest']:.1f} to {sync.loc['Network + CPP', 'latest']:.1f}"),
    ("ToU tariff (17.0\\%)", f"{ovl.loc['Static ToU', 'mixed']:.1f}"),
    ("network price\n(37.2--38.2\\%)",
     f"{ovl.loc[['Network, no CPP', 'Network + CPP'], 'mixed'].min():.1f}-"
     f"{ovl.loc[['Network, no CPP', 'Network + CPP'], 'mixed'].max():.1f}"),
    ("gives 13.3\\%", f"{ovl.loc['Network + dither', 'latest']:.1f}"),
    ("gives\n6.2\\%", f"{ovl.loc['Network + dither 5p', 'latest']:.1f}"),
    ("feeder has room for about ten chargers",
     f"{(P_MAX - ex['background_kw'].to_numpy().reshape(48, 30).mean(1).min()) / 7.4:.1f}"),
    ("this day 11 chargers switched on together at 00:30",
     f"{ex['Static ToU'].diff().max() / 7.4:.0f} at minute {ex['Static ToU'].diff().idxmax()}"),
    ("reaches 106~kW at 03:00",
     f"{(ex['background_kw'] + ex['Network, no CPP']).to_numpy().reshape(48, 30).mean(1).max():.0f}"),
    ("(11 chargers at 03:30)",
     f"{ex['Network + CPP'].diff().max() / 7.4:.0f} at minute {ex['Network + CPP'].diff().idxmax()}"),
    ("from 129~kW", f"{m(100, 'Uncontrolled', 'cvar95_peak30_kw'):.0f}"),
    ("to 147--151~kW", f"{m(100, 'Static ToU', 'cvar95_peak30_kw'):.0f}-"
                       f"{m(100, 'Network + CPP', 'cvar95_peak30_kw'):.0f}"),
    ("The delay left 36\\% of days", f"{m(100, 'Network + CPP + delay 600 s', 'p_overload_pct'):.0f}"),
    ("dither 7.0\\%", f"{m(100, 'Network + dither', 'p_overload_pct'):.1f}"),
    ("quota 5.5\\%", f"{m(100, 'Quota + price (hybrid)', 'p_overload_pct'):.1f}"),
    ("0.29\\% of energy", f"{m(100, 'Quota + price (hybrid)', 'unserved_pct'):.2f}"),
    ("24.7\\% to 6.4--7.8\\%", f"{share.loc[(0.0, 'Static ToU'), 'p_overload_pct']:.1f} -> "
                             f"{share.loc[(0.5, 'Network + CPP'), 'p_overload_pct']:.1f}-"
                             f"{share.loc[(0.5, 'Static ToU'), 'p_overload_pct']:.1f}"),
    ("15.5--19.1\\%", f"{share.loc[(1.0, 'Static ToU'), 'p_overload_pct']:.1f}-"
                     f"{share.loc[(1.0, 'Agile'), 'p_overload_pct']:.1f}"),
    ("124--128~kW", f"{share.loc[(1.0, 'Static ToU'), 'cvar95_peak30_kw']:.0f}-"
                    f"{share.loc[(1.0, 'Network + CPP'), 'cvar95_peak30_kw']:.0f}"),
    ("the 122~kW", f"{share.loc[(1.0, 'Uncontrolled'), 'cvar95_peak30_kw']:.0f}"),
    ("at most 1.3 surcharged", f"{max(last10('smart_share', s)['slots_changed'] for s in (0, .25, .5)):.1f}"),
    ("at most\n1.6~kW", f"{max(last10('smart_share', s)['max_change_kw'] for s in (0, .25, .5)):.1f}"),
    ("3.0 slots changed", f"{last10('smart_share', 1.0)['slots_changed']:.1f}"),
    ("moved by 14.8~kW", f"{last10('smart_share', 1.0)['max_change_kw']:.1f}"),
    ("4.7 slots and 17.4~kW", f"{last10('fixed_point', 1.0, 100)['slots_changed']:.1f} / "
                              f"{last10('fixed_point', 1.0, 100)['max_change_kw']:.1f}"),
    ("(41.5\\% with it, 41.2\\% without)", f"{m(100, 'Network + CPP', 'p_overload_pct'):.1f} / "
                                          f"{m(100, 'Network, no CPP', 'p_overload_pct'):.1f}"),
    ("4.7 to 9.0", f"{m(100, 'Network, no CPP', 'max_switch_on_chargers'):.1f} -> "
                   f"{m(100, 'Network + CPP', 'max_switch_on_chargers'):.1f}"),
    ("from 9.0 to 2.7 chargers", f"{m(100, 'Network + CPP + delay 600 s', 'max_switch_on_chargers'):.1f}"),
    ("36.3\\% of\ndays", f"{m(100, 'Network + CPP + delay 600 s', 'p_overload_pct'):.1f}"),
    ("28.9\\% and 39.2\\%", f"{m(100, 'Network + CPP + delay 600 s', 'p_overload_min'):.2f} / "
                           f"{m(100, 'Network + CPP + delay 600 s', 'p_overload_max'):.2f}"),
    ("left 1.45\\%", f"{m(100, 'Network + CPP + delay 1800 s', 'unserved_pct'):.2f}"),
    ("2.0\\% at 80\\% ownership and 7.0\\%", f"{m(80, 'Network + dither', 'p_overload_pct'):.1f} / "
                                           f"{m(100, 'Network + dither', 'p_overload_pct'):.1f}"),
    ("(9.4\\%)", f"{m(100, 'Network + CPP + dither', 'p_overload_pct'):.1f}"),
    ("(19.3\\%)", f"{m(100, 'Network + CPP + dither', 'p_overload_max'):.1f}"),
    ("from 8.75 to\n8.34", f"{dither.loc[0.0, 'price_paid_p_kwh']:.2f} -> {dither.loc[2.0, 'price_paid_p_kwh']:.2f}"),
    ("5.5\\%\noverload days and a $\\CVaR_{95}$ of 102~kW", f"{m(100, 'Quota + price (hybrid)', 'cvar95_peak30_kw'):.0f}"),
    ("8.6\\%\nand 107~kW", f"{m(100, 'Quota (ASAP)', 'p_overload_pct'):.1f} / "
                          f"{m(100, 'Quota (ASAP)', 'cvar95_peak30_kw'):.0f}"),
    ("145--149~kW at 100\\%, against 130~kW", f"{pen.loc[(100, 'Static ToU'), 'cvar95_peak30_kw']:.0f}-"
                                            f"{pen.loc[(100, 'Network + CPP'), 'cvar95_peak30_kw']:.0f} vs "
                                            f"{pen.loc[(100, 'Uncontrolled'), 'cvar95_peak30_kw']:.0f}"),
    ("within 1~kW of the firm limit up to 80\\%", f"{pen.loc[(80, 'Network + dither'), 'cvar95_peak30_kw']:.1f}"),
    ("(103~kW at 100\\%)", f"{pen.loc[(100, 'Quota + price (hybrid)'), 'cvar95_peak30_kw']:.0f}"),
    ("2.7\\% at $\\pm$5\\pkwh{} and 1.2\\%", f"{dither.loc[5.0, 'p_overload_pct']:.1f} / "
                                            f"{dither.loc[10.0, 'p_overload_pct']:.1f}"),
    ("1.42\\pkwh{} at", f"{dither.loc[0.0, 'price_paid_p_kwh'] - dither.loc[5.0, 'price_paid_p_kwh']:.2f}"),
    ("26.0\\% to 1.0\\%", f"{hyb.loc[0.5, 'p_overload_pct']:.1f} -> {hyb.loc[0.99, 'p_overload_pct']:.1f}"),
    ("0.20\\% to 0.31\\%", f"{hyb.loc[0.5, 'unserved_pct']:.2f} -> {hyb.loc[0.99, 'unserved_pct']:.2f}"),
]


def main():
    missing = 0
    for phrase, value in CHECKS:
        found = " ".join(phrase.split()) in TEX
        missing += not found
        print(f"[{'ok ' if found else 'MISSING'}] {phrase.replace(chr(10), ' ')!r:55s} results: {value}")
    print(f"\n{len(CHECKS) - missing}/{len(CHECKS)} phrases found; compare each with its value.")


if __name__ == "__main__":
    main()
