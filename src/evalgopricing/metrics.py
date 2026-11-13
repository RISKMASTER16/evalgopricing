"""Network and service metrics over a set of simulated days."""
import numpy as np


def cvar(x, alpha=0.95):
    x = np.sort(np.asarray(x))
    var = np.quantile(x, alpha)
    return x[x >= var].mean()


def summarise(results, inp, keep_profile=True):
    pmax = inp["p_max_kw"]
    P = inp["charger_kw"]
    tot = np.array([r.total for r in results])          # days x 1440
    ev = np.array([r.ev for r in results])
    tot30 = tot.reshape(len(results), 48, 30).mean(axis=2)
    peak30 = tot30.max(axis=1)
    peak1 = tot.max(axis=1)
    exceed = np.maximum(tot30 - pmax, 0).sum(axis=1) * 0.5
    # largest one-minute rise in EV load, in chargers (circular day)
    rise = (ev - np.roll(ev, 1, axis=1)).max(axis=1) / P
    req = sum(r.requested for r in results)
    dlv = sum(r.delivered for r in results)
    out = {
        "days": len(results),
        "mean_peak30_kw": peak30.mean(),
        "cvar95_peak30_kw": cvar(peak30),
        "p_overload_pct": 100 * (peak30 > pmax).mean(),
        "exceed_kwh_day": exceed.mean(),
        "mean_peak1_kw": peak1.mean(),
        "max_switch_on_chargers": rise.mean(),
        "unserved_pct": 100 * max(req - dlv, 0.0) / req if req > 0 else 0.0,
        "energy_mwh": dlv / 1000,
        "price_paid_p_kwh": sum(r.cost for r in results)
        / max(sum(r.ev.sum() for r in results) / 60.0, 1e-9),
    }
    profile = ev.mean(axis=0) if keep_profile else None
    return out, profile
