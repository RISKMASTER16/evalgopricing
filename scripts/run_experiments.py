"""Run every experiment and write the results to results/.

    python scripts/run_experiments.py [--quick]
"""
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

from evalgopricing import (Mechanism, load_inputs, sample_days, simulate_day,
                       solve_surcharge, summarise)

RES = ROOT / "results"
GEN = ROOT / "data" / "generated"
H = 75
EVAL_SEED = 2027
FP_SEED = 500
LAST_ROUNDS = 10   # surcharge tariffs are evaluated over the last 10 rounds


def n_ev(pen):
    return int(round(H * pen / 100))


def nonsmart_forecast(inp, nev, s, n_days=400):
    """Operator's forecast of uncontrollable (non-smart) EV load, kW/minute."""
    if s >= 1.0:
        return None
    days = sample_days(n_days, nev, inp, seed=9)
    m = Mechanism("legacy", "flat", 0.0)
    prof = np.mean([simulate_day(d, m, inp).ev for d in days], axis=0)
    return prof * (1.0 - s)


def build_mechanisms(inp, nev, s, fp_log, tag, dither=None, quota_q=0.9):
    """Every mechanism compared in the paper, with surcharges solved by the
    damped fixed point for the response each mechanism induces."""
    dither = inp["dither_p"] if dither is None else dither

    def fp(name, **kw):
        _, hist, rounds = solve_surcharge(inp, nev, Mechanism(name, "network", s, **kw),
                                          FP_SEED)
        for h in hist:
            fp_log.append({"case": tag, "mechanism": name, "smart_share": s,
                           "penetration": round(100 * nev / H), **h})
        return rounds[-LAST_ROUNDS:]

    ns = nonsmart_forecast(inp, nev, s)
    return [
        Mechanism("Uncontrolled", "flat", 0.0),
        Mechanism("Static ToU", "tou", s),
        Mechanism("Agile", "agile", s),
        Mechanism("Network, no CPP", "network", s),
        (Mechanism("Network + CPP", "network", s), fp("Network + CPP")),
        (Mechanism("Network + CPP + delay 600 s", "network", s, delay_s=600),
         fp("Network + CPP + delay 600 s", delay_s=600)),
        (Mechanism("Network + CPP + delay 1800 s", "network", s, delay_s=1800),
         fp("Network + CPP + delay 1800 s", delay_s=1800)),
        (Mechanism("Network + CPP + dither", "network", s, dither_p=dither),
         fp("Network + CPP + dither", dither_p=dither)),
        Mechanism("Network + dither", "network", s, dither_p=dither),
        Mechanism("Quota (ASAP)", "network", s, quota="asap", quota_quantile=quota_q,
                  nonsmart_forecast=ns),
        Mechanism("Quota + price (hybrid)", "network", s, quota="price",
                  quota_quantile=quota_q, nonsmart_forecast=ns),
    ]


def evaluate(mechs, days, inp, extra, profiles=None, example=None):
    """Evaluate each mechanism on the same days. A (mechanism, surcharges)
    pair is evaluated once per surcharge (one per fixed-point round) and the
    metrics are averaged; the overload range across rounds is also kept."""
    rows = []
    for item in mechs:
        m, cpps = item if isinstance(item, tuple) else (item, [None])
        outs, profs = [], []
        for c in cpps:
            mm = Mechanism(**{**m.__dict__, "cpp": c})
            res = [simulate_day(d, mm, inp) for d in days]
            out, prof = summarise(res, inp, keep_profile=profiles is not None)
            outs.append(out)
            profs.append(prof)
        avg = {k: float(np.mean([o[k] for o in outs])) for k in outs[0]}
        ovl = [o["p_overload_pct"] for o in outs]
        cv = [o["cvar95_peak30_kw"] for o in outs]
        rows.append({**extra, "mechanism": m.name, **avg, "tariffs_evaluated": len(outs),
                     "p_overload_min": min(ovl), "p_overload_max": max(ovl),
                     "cvar95_min": min(cv), "cvar95_max": max(cv)})
        if profiles is not None:
            profiles[m.name] = np.mean(profs, axis=0)
        if example is not None:
            example[m.name] = res[example["_day"]].ev
    return rows


def scheduler_sensitivity(inp, n_days, fp_log):
    """Repeat the key comparison with a commercial-style scheduler (whole
    half-hours, ties broken latest, one-hour buffer) and a 50/50 fleet."""
    rows = []
    for pen in (80, 100):
        nev = n_ev(pen)
        days = sample_days(n_days, nev, inp, EVAL_SEED + 30 + pen)
        rows += evaluate([Mechanism("Uncontrolled", "flat", 0.0)], days, inp,
                         {"penetration": pen, "scheduler": "none"})
        for sch in ("earliest", "latest", "mixed"):
            kw = {"scheduler": sch}
            _, hist, rounds = solve_surcharge(
                inp, nev, Mechanism("Network + CPP", "network", 1.0, **kw), FP_SEED)
            for h in hist:
                fp_log.append({"case": f"scheduler_{sch}", "mechanism": "Network + CPP",
                               "smart_share": 1.0, "penetration": pen, **h})
            mechs = [Mechanism("Static ToU", "tou", 1.0, **kw),
                     Mechanism("Agile", "agile", 1.0, **kw),
                     Mechanism("Network, no CPP", "network", 1.0, **kw),
                     (Mechanism("Network + CPP", "network", 1.0, **kw),
                      rounds[-LAST_ROUNDS:]),
                     Mechanism("Network + dither", "network", 1.0,
                               dither_p=inp["dither_p"], **kw),
                     Mechanism("Network + dither 5p", "network", 1.0, dither_p=5.0, **kw)]
            rows += evaluate(mechs, days, inp, {"penetration": pen, "scheduler": sch})
    return rows


def main(quick=False, only=None):
    t0 = time.time()
    inp = load_inputs()
    RES.mkdir(exist_ok=True)
    GEN.mkdir(parents=True, exist_ok=True)
    D_MAIN = 300 if quick else 2000
    D_SWEEP = 200 if quick else 1000
    if only == "scheduler":
        fp_log = []
        rows = scheduler_sensitivity(inp, D_SWEEP, fp_log)
        pd.DataFrame(rows).to_csv(RES / "scheduler_sensitivity.csv", index=False)
        print(f"scheduler sensitivity done {time.time() - t0:.0f}s")
        return
    fp_log = []
    main_rows = []
    for pen in (60, 80, 100):
        nev = n_ev(pen)
        days = sample_days(D_MAIN, nev, inp, EVAL_SEED + pen)
        mechs = build_mechanisms(inp, nev, 1.0, fp_log, f"main_p{pen}")
        profiles = {} if pen == 80 else None
        example = {"_day": int(np.argmax([d.xi for d in days[:200]]))} if pen == 80 else None
        main_rows += evaluate(mechs, days, inp, {"penetration": pen, "smart_share": 1.0},
                              profiles, example)
        if pen == 80:
            minute = np.arange(1440)
            pd.DataFrame({"minute": minute, **profiles}).to_csv(
                RES / "mean_ev_profile_p80.csv", index=False)
            ex = {k: v for k, v in example.items() if k != "_day"}
            bg_min = np.repeat(days[example["_day"]].background, 30).round(3)
            pd.DataFrame({"minute": minute, "background_kw": bg_min, **ex}).to_csv(
                RES / "example_day_ev_p80.csv", index=False)
            # a slice of the simulated sessions, published as a dataset
            sess = []
            for i, d in enumerate(days[:200]):
                sess.append(pd.DataFrame({"day": i, "plug_in_min": d.arrive,
                                          "dwell_min": d.dwell,
                                          "energy_kwh": d.energy.round(3)}))
            pd.concat(sess).to_csv(GEN / "sessions_sample_p80.csv", index=False)
        print(f"main p={pen} done {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(main_rows).to_csv(RES / "main_results.csv", index=False)
    rows = []
    nev = n_ev(80)
    days = sample_days(D_SWEEP, nev, inp, EVAL_SEED + 1)
    for s in (0.0, 0.25, 0.5, 0.75, 1.0):
        mechs = build_mechanisms(inp, nev, s, fp_log, "smart_share")
        keep = {"Uncontrolled", "Static ToU", "Agile", "Network + CPP",
                "Network + CPP + delay 600 s", "Network + dither",
                "Quota + price (hybrid)"}
        name = lambda it: (it[0] if isinstance(it, tuple) else it).name
        rows += evaluate([m for m in mechs if name(m) in keep], days, inp,
                         {"penetration": 80, "smart_share": s})
    pd.DataFrame(rows).to_csv(RES / "smart_share_sweep.csv", index=False)
    print(f"smart-share sweep done {time.time() - t0:.0f}s", flush=True)
    rows = []
    for pen in (20, 40, 60, 80, 100):
        nev = n_ev(pen)
        days = sample_days(D_SWEEP, nev, inp, EVAL_SEED + 10 + pen)
        rows += evaluate(build_mechanisms(inp, nev, 1.0, fp_log, "penetration"), days, inp,
                         {"penetration": pen, "smart_share": 1.0})
    pd.DataFrame(rows).to_csv(RES / "penetration_sweep.csv", index=False)
    print(f"penetration sweep done {time.time() - t0:.0f}s", flush=True)
    rows = []
    for pen in (80, 100):
        nev = n_ev(pen)
        days = sample_days(D_SWEEP, nev, inp, EVAL_SEED + 20 + pen)
        for q in (0.5, 0.7, 0.8, 0.9, 0.95, 0.99):
            for kind, label in (("asap", "Quota (ASAP)"), ("price", "Quota + price (hybrid)")):
                m = Mechanism(label, "network", 1.0, quota=kind, quota_quantile=q)
                rows += evaluate([m], days, inp, {"penetration": pen, "instrument": "quantity",
                                                  "setting": q})
        for dp in (0.0, 0.5, 1.0, 2.0, 5.0, 10.0):
            m = Mechanism("Network + dither", "network", 1.0, dither_p=dp)
            rows += evaluate([m], days, inp, {"penetration": pen, "instrument": "price",
                                              "setting": dp})
        for ds in (600, 1800):
            m = Mechanism(f"Network + delay {ds} s", "network", 1.0, delay_s=ds)
            rows += evaluate([m], days, inp, {"penetration": pen, "instrument": "delay",
                                              "setting": ds})
    pd.DataFrame(rows).to_csv(RES / "remedy_settings.csv", index=False)
    print(f"frontier done {time.time() - t0:.0f}s", flush=True)
    rows = scheduler_sensitivity(inp, D_SWEEP, fp_log)
    pd.DataFrame(rows).to_csv(RES / "scheduler_sensitivity.csv", index=False)
    print(f"scheduler sensitivity done {time.time() - t0:.0f}s", flush=True)
    for pen in (80, 100):
        for s in (0.0, 1.0):
            _, hist, _ = solve_surcharge(inp, n_ev(pen),
                                         Mechanism("Network + CPP", "network", s), FP_SEED)
            for h in hist:
                fp_log.append({"case": "fixed_point", "mechanism": "Network + CPP",
                               "smart_share": s, "penetration": pen, **h})
    pd.DataFrame(fp_log).to_csv(RES / "fixed_point_history.csv", index=False)
    print(f"all done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", choices=["scheduler"], default=None,
                    help="run only one experiment")
    main(**vars(ap.parse_args()))
