"""Solve the network-aware critical-peak surcharge by damped fixed-point iteration."""
import numpy as np

from .charging import Mechanism, simulate_day
from .demand import sample_days
from . import tariffs


def solve_surcharge(inp, n_ev, mech: Mechanism, seed):
    S = int(inp["fp_scenarios"])
    M = int(inp["fp_rounds"])
    a = inp["fp_damping"]
    q = inp["cpp_quantile"]
    D = np.zeros(48)
    Dq = np.zeros(48)
    history = []
    rounds = []
    prev_c = None
    for m in range(M):
        c = tariffs.cpp(Dq, inp)
        trial = Mechanism(**{**mech.__dict__, "price": "network", "cpp": c})
        days = sample_days(S, n_ev, inp, seed + 1000 * m)
        Y = np.array([simulate_day(d, trial, inp).ev.reshape(48, 30).mean(1) for d in days])
        newD = (1 - a) * D + a * Y.mean(0)
        newDq = (1 - a) * Dq + a * np.quantile(Y, q, axis=0)
        history.append({
            "round": m + 1,
            "mean_ev_kw": newD.mean(),
            "max_change_kw": np.abs(newD - D).max(),
            "q90_peak_kw": newDq.max(),
            "surcharged_slots": int((c > 0).sum()),
            "slots_changed": int(0 if prev_c is None else (c != prev_c).sum()),
        })
        prev_c = c
        D, Dq = newD, newDq
        rounds.append(tariffs.cpp(Dq, inp))
    return rounds[-1], history, rounds
