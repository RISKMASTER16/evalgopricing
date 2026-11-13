"""Session-level Monte Carlo model of home EV charging and household load.

Each day is a 24 h circular clock: sessions running past midnight wrap round.
"""
from dataclasses import dataclass

import numpy as np

from .config import Inputs, lognormal_from_mean_cv, MIN_PER_DAY


@dataclass
class Day:
    background: np.ndarray   # realised non-EV load, kW, 48 slots
    xi: float                # day factor applied to the background
    arrive: np.ndarray       # plug-in minute (0..1439)
    dwell: np.ndarray        # minutes plugged in
    energy: np.ndarray       # battery energy requested, kWh (feasible)
    u_smart: np.ndarray      # uniform draw; session is smart if u_smart < s
    rng_seed: int            # seed for mechanism-specific randomness

    @property
    def n(self):
        return len(self.arrive)


def sample_sessions(rng, n_ev, inp: Inputs):
    p = inp.p
    n = rng.poisson(n_ev * p["sessions_per_vehicle_day"])
    # distance since the last charge is sampled as one day's driving and
    # scaled by 1/k below (a car charging every 1/k days)
    sig_d = p["mileage_sigma"]
    mu_d = np.log(p["mileage_mean_km_day"]) - sig_d ** 2 / 2
    km = rng.lognormal(mu_d, sig_d, n)
    soc = np.clip(rng.lognormal(np.log(p["soc_median"]), p["soc_sigma"], n), 0.02, 0.95)
    comp = rng.choice(len(inp.mix_w), size=n, p=inp.mix_w / inp.mix_w.sum())
    a_h = rng.normal(inp.mix_mu[comp], inp.mix_sd[comp]) % 24.0
    # departure: evening/overnight arrivals leave next morning, daytime
    # arrivals stay for a few hours
    overnight = (a_h >= 14.0) | (a_h < 4.0)
    dep = np.clip(rng.normal(p["departure_mean_h"], p["departure_sd_h"], n), 5.0, 10.0)
    dwell_h = np.where(overnight, (dep - a_h) % 24.0,
                       rng.uniform(p["daytime_dwell_min_h"], p["daytime_dwell_max_h"], n))
    dwell_h = np.maximum(dwell_h, 1.0)
    energy = (1 - soc) * km * p["consumption_kwh_per_100km"] / 100 / p["sessions_per_vehicle_day"]
    energy = np.minimum(energy, (1 - soc) * p["battery_kwh"])
    # keep only what can physically be delivered in the dwell at full power,
    # so any unserved energy is caused by the mechanism, not the request
    arrive = np.round(a_h * 60).astype(int) % MIN_PER_DAY
    dwell = np.floor(dwell_h * 60).astype(int)
    energy = np.minimum(energy, dwell / 60.0 * p["charger_kw"] * p["efficiency"])
    return arrive, dwell, energy, rng.random(n)


def sample_background(rng, inp: Inputs):
    p = inp.p
    mu, sig = lognormal_from_mean_cv(1.0, p["background_day_cv"])
    xi = rng.lognormal(mu, sig)
    mu_e, sig_e = lognormal_from_mean_cv(1.0, p["background_slot_cv"])
    eps = rng.lognormal(mu_e, sig_e, 48)
    return inp.background * xi * eps, xi


def sample_days(n_days, n_ev, inp: Inputs, seed):
    """Draw n_days independent days. The same seed gives the same days, so
    every mechanism is compared on identical demand (common random numbers)."""
    rng = np.random.default_rng(seed)
    days = []
    for _ in range(n_days):
        bg, xi = sample_background(rng, inp)
        a, w, e, u = sample_sessions(rng, n_ev, inp)
        days.append(Day(bg, xi, a, w, e, u, int(rng.integers(2**31))))
    return days
