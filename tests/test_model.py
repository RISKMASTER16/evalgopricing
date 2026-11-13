"""Sanity checks for the model."""
import numpy as np

from evalgopricing import Mechanism, load_inputs, sample_days, simulate_day
from evalgopricing.charging import quota_cap

INP = load_inputs()
DAYS = sample_days(40, 60, INP, seed=3)


def test_energy_conserved_for_price_responses():
    for m in [Mechanism("u", "flat", 0.0), Mechanism("t", "tou", 1.0),
              Mechanism("a", "agile", 1.0), Mechanism("n", "network", 1.0, dither_p=2.0)]:
        for d in DAYS:
            r = simulate_day(d, m, INP)
            assert abs(r.delivered - r.requested) < 1e-6
            grid_kwh = r.ev.sum() / 60.0
            assert abs(grid_kwh * INP["efficiency"] - r.delivered) < 1e-6


def test_quota_never_exceeds_released_capacity():
    m = Mechanism("q", "network", 1.0, quota="price", quota_quantile=0.9)
    cap = quota_cap(m, INP)
    for d in DAYS:
        r = simulate_day(d, m, INP)
        assert np.all(r.ev <= cap + 1e-9)


def test_same_seed_same_days():
    a = sample_days(3, 60, INP, seed=11)
    b = sample_days(3, 60, INP, seed=11)
    assert all(np.array_equal(x.energy, y.energy) for x, y in zip(a, b))


def test_smart_chargers_move_energy_into_cheap_window():
    cheap = np.zeros(1440, bool)
    cheap[30:330] = True                    # 00:30-05:30
    smart = sum(simulate_day(d, Mechanism("t", "tou", 1.0), INP).ev[cheap].sum()
                for d in DAYS)
    plain = sum(simulate_day(d, Mechanism("u", "flat", 0.0), INP).ev[cheap].sum()
                for d in DAYS)
    assert smart > 2 * plain


def test_commercial_scheduler_conserves_energy_and_books_half_hours():
    from evalgopricing.charging import _latest_positions
    for sch in ("latest", "mixed"):
        m = Mechanism("n", "network", 1.0, scheduler=sch, dither_p=2.0)
        for d in DAYS:
            r = simulate_day(d, m, INP)
            assert abs(r.delivered - r.requested) < 1e-6
    pm = np.repeat([5.0, 1.0, 1.0, 3.0], 30)            # four half-hours, a tie
    pos, need = _latest_positions(pm, arrive=0, W=120, need=20, buffer_min=60)
    assert need == 20
    assert np.array_equal(pos, np.arange(30, 120))      # 20 + 60 min: three slots
    pos, _ = _latest_positions(pm, arrive=0, W=120, need=10, buffer_min=0)
    assert np.array_equal(pos, np.arange(60, 90))       # tie broken by the later slot
