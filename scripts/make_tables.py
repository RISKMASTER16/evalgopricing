"""Write the LaTeX body of Table II to results/table_main.tex."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ROWS = [
    ("Uncontrolled", "Uncontrolled"),
    ("Static ToU", "Static ToU"),
    ("Agile", "Agile"),
    ("Network, no CPP", "Network, no CPP"),
    ("Network + CPP", "Network + CPP"),
    ("Network + CPP + delay 600 s", "\\quad + 600 s delay"),
    ("Network + CPP + delay 1800 s", "\\quad + 1800 s delay"),
    ("Network + CPP + dither", "\\quad + dither"),
    ("Network + dither", "Network + dither"),
    ("Quota (ASAP)", "Quota (ASAP)"),
    ("Quota + price (hybrid)", "Hybrid quota"),
]


def main():
    df = pd.read_csv(ROOT / "results" / "main_results.csv").set_index(["penetration", "mechanism"])
    lines = []
    for key, label in ROWS:
        a, b = df.loc[(80, key)], df.loc[(100, key)]
        lines.append(
            f"{label} & {a.p_overload_pct:.1f} & {a.cvar95_peak30_kw:.0f} & "
            f"{b.p_overload_pct:.1f} & {b.cvar95_peak30_kw:.0f} & "
            f"{b.max_switch_on_chargers:.1f} & {b.unserved_pct:.2f}\\\\")
    out = ROOT / "results" / "table_main.tex"
    out.write_text("\n".join(lines) + "\n")
    print(out.read_text())


def scheduler_table():
    """Write the body of the scheduler table to results/table_scheduler.tex."""
    d = pd.read_csv(ROOT / "results" / "scheduler_sensitivity.csv")
    d = d[d.penetration == 100].pivot_table(index="mechanism", columns="scheduler",
                                            values="p_overload_pct")
    names = [("Static ToU", "Time-of-use"), ("Agile", "Agile"),
             ("Network, no CPP", "Network, no CPP"), ("Network + CPP", "Network + CPP"),
             ("Network + dither", "Network + dither $\\pm$2"),
             ("Network + dither 5p", "Network + dither $\\pm$5")]
    rows = [f"Uncontrolled & \\multicolumn{{3}}{{c}}{{{d.loc['Uncontrolled', 'none']:.1f}}}\\\\"]
    rows += [f"{lab} & {d.loc[k, 'earliest']:.1f} & {d.loc[k, 'latest']:.1f} & "
            f"{d.loc[k, 'mixed']:.1f}\\\\" for k, lab in names]
    (ROOT / "results" / "table_scheduler.tex").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
    scheduler_table()
