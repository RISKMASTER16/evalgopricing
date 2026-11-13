"""Day-ahead tariffs on 48 half-hourly slots, in p/kWh."""
import numpy as np

from .config import Inputs, lognormal_from_mean_cv


def flat(inp: Inputs):
    return np.full(48, inp["flat_p"])


def static_tou(inp: Inputs):
    """Octopus Go structure: cheap 00:30-05:30, flat otherwise."""
    price = np.full(48, inp["go_peak_p"])
    price[1:11] = inp["go_offpeak_p"]
    return price


def wholesale_day(rng, inp: Inputs):
    """Synthetic day-ahead wholesale price (p/kWh) for one day."""
    mu, sig = lognormal_from_mean_cv(inp["wholesale_mean_p"], inp["wholesale_day_cv"])
    level = rng.lognormal(mu, sig)
    mu_e, sig_e = lognormal_from_mean_cv(1.0, inp["wholesale_slot_cv"])
    w = level * inp.wholesale_shape * rng.lognormal(mu_e, sig_e, 48)
    if rng.random() < inp["negative_night_share"]:
        w[2:10] = -rng.uniform(0.0, 3.0, 8)   # 01:00-05:00 negative prices
    return w


def agile(wholesale, inp: Inputs):
    """Agile Octopus formula applied to a wholesale price."""
    peak = np.zeros(48)
    peak[32:38] = inp["agile_peak_adder_p"]          # 16:00-19:00
    price = inp["agile_multiplier"] * wholesale + inp["agile_offset_p"] + peak
    return np.minimum(price, inp["agile_cap_p"])


def network_base(inp: Inputs):
    """Network-aware base price T(i) = C1 * forecast background load,
    with C1 set so the price at the background peak is na_peak_price_p."""
    bg = inp.background
    return inp["na_peak_price_p"] * bg / bg.max()


def surplus(inp: Inputs):
    return np.maximum(inp["p_max_kw"] - inp.background, 1e-6)


def cpp(ev_forecast_q, inp: Inputs):
    """Critical-peak surcharge from forecast EV load (kW, 48 slots)."""
    u = ev_forecast_q / surplus(inp)
    out = np.zeros(48)
    out[u >= inp["cpp_threshold"]] = inp["cpp_tier_p"]
    out[u >= 1.0] = inp["cpp_max_p"]
    return out
