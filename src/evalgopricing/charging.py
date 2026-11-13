"""Turn a price into each charger's one-minute power profile."""
from dataclasses import dataclass, field

import numpy as np

from .config import Inputs, MIN_PER_DAY, slot_to_minutes, lognormal_from_mean_cv
from .demand import Day
from . import tariffs


@dataclass
class Mechanism:
    name: str
    price: str = "flat"            # flat | tou | agile | network
    smart_share: float = 1.0
    delay_s: float = 0.0
    dither_p: float = 0.0
    quota: str | None = None       # None | "asap" | "price"
    quota_quantile: float = 0.9
    scheduler: str = "earliest"    # earliest | latest | mixed
    latest_share: float = 0.5      # share of "latest" schedulers when mixed
    buffer_min: float = 60.0       # extra charge time the "latest" scheduler books
    cpp: np.ndarray | None = None  # surcharge (48) for the network price
    nonsmart_forecast: np.ndarray | None = field(default=None, repr=False)


@dataclass
class DayResult:
    ev: np.ndarray          # EV load, kW, 1440 minutes
    total: np.ndarray       # EV + background, kW, 1440 minutes
    requested: float        # kWh (battery side)
    delivered: float        # kWh (battery side)
    price: np.ndarray       # day-ahead price seen, 48 slots
    cost: float = 0.0       # pence paid by all sessions (grid side)


def day_price(day: Day, mech: Mechanism, inp: Inputs):
    if mech.price == "flat":
        return tariffs.flat(inp)
    if mech.price == "tou":
        return tariffs.static_tou(inp)
    if mech.price == "agile":
        rng_w = np.random.default_rng(day.rng_seed)
        return tariffs.agile(tariffs.wholesale_day(rng_w, inp), inp)
    if mech.price == "network":
        c = mech.cpp if mech.cpp is not None else np.zeros(48)
        return tariffs.network_base(inp) + c
    raise ValueError(mech.price)


def _place(load, positions, idx, need, P, pm):
    """Add a session drawing P over `need` minutes, taking window positions in
    the given order. `pm` is the price (p/kWh) the session pays in each window
    minute. Returns (minutes placed, pence paid)."""
    need = min(need, len(positions))
    full = int(np.floor(need))
    load[idx[positions[:full]]] += P
    cost = pm[positions[:full]].sum() * P / 60.0
    frac = need - full
    if frac > 1e-9:
        load[idx[positions[full]]] += P * frac
        cost += pm[positions[full]] * P * frac / 60.0
    return need, cost


def _delayed_positions(order, need, W, rng, delay_min_max):
    """Positions chosen by a smart charger, with each switch-on delayed by a
    random 0..delay_min_max minutes and each block's length kept."""
    full = int(np.ceil(min(need, W)))
    chosen = np.zeros(W, bool)
    chosen[order[:full]] = True
    # contiguous blocks in window order
    d = np.diff(np.concatenate(([0], chosen.view(np.int8), [0])))
    starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    out = np.zeros(W, bool)
    for s, e in zip(starts, ends):
        shift = int(np.round(rng.uniform(0, delay_min_max)))
        out[min(s + shift, W):min(e + shift, W)] = True
    pos = np.flatnonzero(out)
    return pos, min(need, len(pos))


def _latest_positions(pm, arrive, W, need, buffer_min):
    """Commercial-style scheduler (ev.energy): book whole half-hours, cheapest
    first with ties broken by the latest time, for the required time plus a
    buffer; the car then charges through the booked half-hours in time order
    until full."""
    slot = (arrive + np.arange(W)) // 30
    _, start, count = np.unique(slot, return_index=True, return_counts=True)
    order = np.lexsort((-start, pm[start]))
    booked = np.cumsum(count[order]) - count[order] < need + buffer_min
    chosen = np.zeros(W, bool)
    for g in order[booked]:
        chosen[start[g]:start[g] + count[g]] = True
    pos = np.flatnonzero(chosen)
    return pos, min(need, len(pos))


def simulate_day(day: Day, mech: Mechanism, inp: Inputs) -> DayResult:
    P = inp["charger_kw"]
    eta = inp["efficiency"]
    price = day_price(day, mech, inp)
    price_min = slot_to_minutes(price)
    rng = np.random.default_rng(day.rng_seed + 1)
    ev = np.zeros(MIN_PER_DAY)
    need_all = day.energy / (P * eta) * 60.0           # minutes at full power
    smart = day.u_smart < mech.smart_share
    if mech.price == "flat":
        smart[:] = False                               # nothing to optimise
    placed = np.zeros(day.n)
    cost = 0.0
    if mech.scheduler == "earliest":
        latest = np.zeros(day.n, bool)
    elif mech.scheduler == "latest":
        latest = np.ones(day.n, bool)
    else:
        u = np.random.default_rng(day.rng_seed + 7).uniform(size=day.n)
        latest = u < mech.latest_share

    if mech.quota is None:
        for j in range(day.n):
            W = int(day.dwell[j])
            idx = (day.arrive[j] + np.arange(W)) % MIN_PER_DAY
            pm = price_min[idx]
            if not smart[j]:
                placed[j], c = _place(ev, np.arange(W), idx, need_all[j], P, pm)
                cost += c
                continue
            if mech.dither_p > 0:
                noise = rng.uniform(-1, 1, 48) * mech.dither_p
                pm = pm + slot_to_minutes(noise)[idx]
            if latest[j]:
                pos, need = _latest_positions(pm, day.arrive[j], W, need_all[j],
                                              mech.buffer_min)
                placed[j], c = _place(ev, pos, idx, need, P, pm)
                cost += c
                continue
            order = np.argsort(pm, kind="stable")
            if mech.delay_s > 0:
                pos, need = _delayed_positions(order, need_all[j], W, rng,
                                               mech.delay_s / 60.0)
                placed[j], c = _place(ev, pos, idx, need, P, pm)
            else:
                placed[j], c = _place(ev, order, idx, need_all[j], P, pm)
            cost += c
    else:
        placed, cost = _quota_day(day, mech, inp, ev, need_all, smart, P, eta,
                                  price_min)

    delivered = float((placed / 60.0 * P * eta).sum())
    total = ev + slot_to_minutes(day.background)
    return DayResult(ev, total, float(day.energy.sum()), delivered, price, cost)


def quota_cap(mech: Mechanism, inp: Inputs):
    """Per-minute EV capacity the operator releases, kW."""
    mu, sig = lognormal_from_mean_cv(1.0, inp["background_day_cv"])
    from scipy.stats import norm
    factor = np.exp(mu + sig * norm.ppf(mech.quota_quantile))
    cap = slot_to_minutes(inp["p_max_kw"] - inp.background * factor)
    if mech.nonsmart_forecast is not None:
        cap = cap - mech.nonsmart_forecast
    return np.maximum(cap, 0.0)


def _quota_day(day, mech, inp, ev, need_all, smart, P, eta, price_min):
    Pmin = inp["charger_min_kw"]
    cap = quota_cap(mech, inp)
    base_min = slot_to_minutes(tariffs.network_base(inp))
    placed = np.zeros(day.n)
    cost = 0.0
    # legacy (non-smart) chargers cannot be controlled
    for j in np.flatnonzero(~smart):
        W = int(day.dwell[j])
        idx = (day.arrive[j] + np.arange(W)) % MIN_PER_DAY
        placed[j], c = _place(ev, np.arange(W), idx, need_all[j], P, price_min[idx])
        cost += c
    # smart chargers reserve capacity in order of plug-in (day starts at noon)
    sm = np.flatnonzero(smart)
    sm = sm[np.argsort((day.arrive[sm] - 720) % MIN_PER_DAY, kind="stable")]
    for j in sm:
        W = int(day.dwell[j])
        idx = (day.arrive[j] + np.arange(W)) % MIN_PER_DAY
        if mech.quota == "price":
            cand = idx[np.argsort(base_min[idx], kind="stable")]
        else:
            cand = idx
        pw = np.minimum(P, cap[cand])
        pw[pw < Pmin] = 0.0
        target = need_all[j] * P              # kW-minutes needed
        cum = np.cumsum(pw)
        k = int(np.searchsorted(cum, target))
        if k >= len(cand):                    # not enough capacity
            use = pw
        else:
            use = pw.copy()
            use[k + 1:] = 0.0
            use[k] = target - (cum[k - 1] if k > 0 else 0.0)
        ev[cand] += use
        cap[cand] -= use
        placed[j] = use.sum() / P
        cost += (use * price_min[cand]).sum() / 60.0
    return placed, cost
