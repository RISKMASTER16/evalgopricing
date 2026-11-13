"""Make every figure from the CSVs in results/.

    python scripts/make_figures.py          # PNG, for the README
    python scripts/make_figures.py --pdf    # vector PDF, for LaTeX
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
FIG = ROOT / "figures"
P_MAX = 100.9
EXT = "pdf" if "--pdf" in sys.argv else "png"
INK = "#333333"
MUTED = "#6b6b6b"

STYLE = {
    "Uncontrolled":                ("Uncontrolled",          "#6b6b6b", "o", (0, (4, 2))),
    "Static ToU":                  ("Time-of-use",           "#2a78d6", "s", "-"),
    "Agile":                       ("Agile",                 "#eb6834", "^", "-"),
    "Network + CPP":               ("Network + CPP",         "#1baf7a", "D", "-"),
    "Network + CPP + delay 600 s": ("Network + CPP + delay", "#eda100", "v", (0, (1, 1))),
    "Network + dither":            ("Network + dither",      "#6250d6", "*", (0, (5, 1.5))),
    "Quota (ASAP)":                ("Quota (ASAP)",          "#e87ba4", "P", (0, (3, 1, 1, 1))),
    "Quota + price (hybrid)":      ("Hybrid quota",          "#008300", "X", (0, (6, 1.5))),
}

plt.rcParams.update({
    "font.family": "STIXGeneral", "mathtext.fontset": "stix",
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "text.color": INK, "axes.labelcolor": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.6,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#e8e8e8",
    "grid.linewidth": 0.5, "lines.linewidth": 1.2, "lines.markersize": 3.5,
    "legend.frameon": False, "legend.handlelength": 2.4,
    "legend.columnspacing": 1.2, "legend.labelspacing": 0.3,
    "savefig.facecolor": "white", "pdf.fonttype": 42,
})


def save(fig, name):
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f"{name}.{EXT}", dpi=300)
    plt.close(fig)


def line(ax, x, y, key, marker=True, **kw):
    label, c, m, ls = STYLE[key]
    ax.plot(x, y, color=c, ls=ls, label=label, marker=m if marker else None,
            markeredgecolor="white", markeredgewidth=0.4, **kw)


def limit(ax, label=True, below=False):
    ax.axhline(P_MAX, color=INK, lw=0.8, ls=(0, (3, 2)), zorder=1)
    if label:
        y = P_MAX - 1.2 if below else P_MAX + 1.5
        ax.text(ax.get_xlim()[1], y, "feeder limit", fontsize=6.5, color=INK,
                ha="right", va="top" if below else "bottom", zorder=6,
                bbox=dict(facecolor="white", edgecolor="none", pad=0.4))


def legend_above(fig, ax, ncol, top=1.0):
    h, lab = ax.get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=ncol, bbox_to_anchor=(0.5, top))


def time_axis(ax):
    ticks = np.arange(0, 25, 3)
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t % 24:02d}:00" for t in ticks])
    ax.set_xlim(0, 24)


def step(a):
    return np.r_[a, a[-1]]


def fig_problem():
    """One cold weekday at 80% EV ownership: uncontrolled, time-of-use and
    the network-aware price with its CPP, half-hourly feeder load."""
    df = pd.read_csv(RES / "example_day_ev_p80.csv")
    bg = df["background_kw"].to_numpy().reshape(48, 30).mean(1)
    x = np.arange(49) / 2
    panels = [("Uncontrolled", "(a) Flat price: drivers charge on arrival"),
              ("Static ToU", "(b) Time-of-use: cheap from 00:30"),
              ("Network + CPP", "(c) Network-aware price with CPP")]
    fig, axs = plt.subplots(3, 1, figsize=(3.5, 2.95), sharex=True, sharey=True)
    for ax, (key, title) in zip(axs, panels):
        ev = df[key].to_numpy().reshape(48, 30).mean(1)
        tot = bg + ev
        ax.fill_between(x, 0, step(bg), step="post", color="#d9d9d9", lw=0,
                        label="Household load")
        ax.fill_between(x, step(bg), step(tot), step="post", color="#2a78d6",
                        alpha=0.85, lw=0, label="EV charging")
        over = tot > P_MAX
        ax.bar(x[:-1][over], (tot - P_MAX)[over], bottom=P_MAX, width=0.5,
               align="edge", color="#c62828", lw=0, label="Over the limit", zorder=3)
        if key == "Network + CPP":
            no_cpp = bg + df["Network, no CPP"].to_numpy().reshape(48, 30).mean(1)
            ax.plot(x, step(no_cpp), drawstyle="steps-post", color=INK, lw=0.8,
                    ls=(0, (1, 1)), label="Same price without CPP")
            emptied = (ev < 1) & (no_cpp - bg > 1)
            for i in np.where(emptied)[0]:
                ax.axvspan(i / 2, i / 2 + 0.5, color="#f6dcdc", lw=0, zorder=0)
            if emptied.any():
                ax.text(np.where(emptied)[0].mean() / 2 + 0.25, 128, "CPP",
                        fontsize=6.5, color="#c62828", ha="center", va="top")
        ax.set_ylim(0, 130)
        ax.set_xlim(0, 24)
        limit(ax, label=key == "Uncontrolled")
        ax.set_title(title, loc="left", pad=2)
        ax.set_yticks([0, 50, 100])
        ax.set_ylabel("Load (kW)")
    time_axis(axs[-1])
    axs[-1].set_xlabel("Time of day")
    h, lab = [], []
    for ax in axs:
        for hh, ll in zip(*ax.get_legend_handles_labels()):
            if ll not in lab:
                h.append(hh)
                lab.append(ll)
    fig.legend(h, lab, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.0),
               handlelength=1.6)
    fig.tight_layout(pad=0.3, h_pad=0.4, rect=(0, 0, 1, 0.9))
    save(fig, "f1_problem")


def fig_profiles():
    df = pd.read_csv(RES / "mean_ev_profile_p80.csv")
    x = np.arange(1440) / 60
    groups = [("(a) Shared prices",
               ["Uncontrolled", "Static ToU", "Agile", "Network + CPP"]),
              ("(b) Mitigations",
               ["Uncontrolled", "Network + CPP + delay 600 s", "Network + dither",
                "Quota + price (hybrid)"])]
    fig, axs = plt.subplots(2, 1, figsize=(3.5, 2.2), sharex=True, sharey=True)
    for ax, (title, keys) in zip(axs, groups):
        for k in keys:
            line(ax, x, df[k].to_numpy(), k, marker=False, lw=1.0)
        ax.set_title(title, loc="left", pad=2)
        ax.set_ylabel("EV load (kW)")
        ax.set_ylim(0, 72)
        ax.legend(loc="upper right", ncol=1, fontsize=6.5, handlelength=2.0)
    time_axis(axs[-1])
    axs[-1].set_xlabel("Time of day")
    fig.tight_layout(pad=0.3, h_pad=0.6)
    save(fig, "f3_profiles")


def fig_smart_share():
    df = pd.read_csv(RES / "smart_share_sweep.csv")
    fig, ax = plt.subplots(figsize=(3.5, 1.8))
    for k in ["Uncontrolled", "Static ToU", "Agile", "Network + CPP",
              "Network + CPP + delay 600 s", "Network + dither", "Quota + price (hybrid)"]:
        d = df[df.mechanism == k].sort_values("smart_share")
        line(ax, 100 * d.smart_share, d.p_overload_pct, k)
    ax.set_xlabel("Share of chargers that are smart (%)")
    ax.set_ylabel("Days over the limit (%)")
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_ylim(0, 28)
    h, lab = ax.get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=4, bbox_to_anchor=(0.52, 1.0),
               fontsize=5.9, handlelength=1.5, columnspacing=0.5, handletextpad=0.4)
    fig.tight_layout(pad=0.3, rect=(0, 0, 1, 0.82))
    save(fig, "f4_smart_share")


def fig_fixed_point():
    df = pd.read_csv(RES / "fixed_point_history.csv")
    d = df[(df.case == "smart_share") & (df.mechanism == "Network + CPP")]
    shades = {0.25: "#9cc3f2", 0.5: "#5a9be6", 0.75: "#1c5cab", 1.0: "#0b2f5c"}
    fig, ax = plt.subplots(figsize=(3.5, 1.5))
    for s_, c in shades.items():
        g = d[d.smart_share == s_].sort_values("round")
        ax.plot(g["round"], g.max_change_kw, color=c, lw=1.1,
                label=f"{int(100 * s_)}% smart")
    ax.set_xlabel("Fixed-point round")
    ax.set_ylabel("Change in EV forecast (kW)")
    ax.set_xlim(1, 30)
    ax.set_ylim(0, 26)
    legend_above(fig, ax, ncol=4)
    fig.tight_layout(pad=0.3, rect=(0, 0, 1, 0.88))
    save(fig, "s1_fixed_point")


def fig_penetration():
    df = pd.read_csv(RES / "penetration_sweep.csv")
    fig, ax = plt.subplots(figsize=(3.5, 1.65))
    for k in ["Uncontrolled", "Static ToU", "Network + CPP", "Network + CPP + delay 600 s",
              "Network + dither", "Quota (ASAP)", "Quota + price (hybrid)"]:
        d = df[df.mechanism == k].sort_values("penetration")
        line(ax, d.penetration, d.cvar95_peak30_kw, k)
    ax.set_xlabel("Households with an EV (%)")
    ax.set_ylabel(r"CVaR$_{95}$ of daily peak (kW)")
    ax.set_xticks([20, 40, 60, 80, 100])
    ax.set_xlim(17, 103)
    ax.set_ylim(85, 152)
    limit(ax, below=True)
    h, lab = ax.get_legend_handles_labels()
    fig.legend(h, lab, loc="upper center", ncol=4, bbox_to_anchor=(0.52, 1.0),
               fontsize=5.9, handlelength=1.5, columnspacing=0.5, handletextpad=0.4)
    fig.tight_layout(pad=0.3, rect=(0, 0, 1, 0.8))
    save(fig, "f5_penetration")


def fig_tradeoffs():
    df = pd.read_csv(RES / "remedy_settings.csv")
    d = df[df.penetration == 100]
    fig, ax = plt.subplots(figsize=(3.5, 1.55))
    note = dict(textcoords="offset points", fontsize=6.5, color=MUTED, va="center")
    p = d[d.instrument == "price"].sort_values("setting")
    line(ax, p.unserved_pct, p.p_overload_pct, "Network + dither")
    for _, r in p[p.setting.isin([0, 10])].iterrows():
        txt = "no dither" if r.setting == 0 else f"$\\pm${r.setting:g} p/kWh"
        ax.annotate(txt, (r.unserved_pct, r.p_overload_pct), xytext=(-5, 0),
                    ha="right", **note)
    for k in ["Quota (ASAP)", "Quota + price (hybrid)"]:
        q = d[d.mechanism == k].sort_values("setting")
        line(ax, q.unserved_pct, q.p_overload_pct, k)
    q = d[d.mechanism == "Quota + price (hybrid)"].sort_values("setting")
    for i, dy in [(0, 4), (-1, 6)]:
        r = q.iloc[i]
        ax.annotate(f"$q$ = {r.setting:g}", (r.unserved_pct, r.p_overload_pct),
                    xytext=(5, dy), ha="left", **note)
    dl = d[d.instrument == "delay"].sort_values("setting")
    _, c, m, _ = STYLE["Network + CPP + delay 600 s"]
    ax.plot(dl.unserved_pct, dl.p_overload_pct, color=c, marker=m, ls="none",
            markersize=5, label="Random delay", markeredgecolor="white",
            markeredgewidth=0.4)
    for _, r in dl.iterrows():
        ax.annotate(f"{r.setting / 60:g} min", (r.unserved_pct, r.p_overload_pct),
                    xytext=(0, -8), ha="center", **note)
    ax.set_xlabel("Energy not delivered by departure (%)")
    ax.set_ylabel("Days over the limit (%)")
    ax.set_xlim(-0.42, 1.38)
    ax.set_xticks([0, 0.4, 0.8, 1.2])
    ax.set_ylim(0, 47)
    legend_above(fig, ax, ncol=2)
    fig.tight_layout(pad=0.3, rect=(0, 0, 1, 0.84))
    save(fig, "f6_tradeoffs")


def main():
    fig_problem()
    fig_profiles()
    fig_smart_share()
    fig_fixed_point()
    fig_penetration()
    fig_tradeoffs()
    print("wrote", sorted(p.name for p in FIG.glob(f"*.{EXT}")))


if __name__ == "__main__":
    main()
