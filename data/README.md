# Data

## inputs/
| File | Contents |
|---|---|
| `parameters.csv` | Every scalar model parameter: name, value, unit, description, source |
| `background_profile.csv` | Forecast non-EV feeder load, 48 half-hourly values (kW). **Stylised** winter weekday shape scaled to a 72.0 kW peak |
| `wholesale_shape.csv` | Normalised day-ahead wholesale price shape, 48 values (mean 1). **Stylised** |
| `plugin_mixture.csv` | Three-component Gaussian mixture of plug-in times (weights, means and standard deviations in hours) |

The two stylised files are produced by `scripts/make_stylised_inputs.py` and can
be replaced with measured data in the same format.

## generated/
| File | Contents |
|---|---|
| `sessions_sample_p80.csv` | 200 simulated days at 80% EV ownership: day, plug-in minute (0-1439), dwell (minutes), energy requested (kWh). These are model outputs, not measurements |

Results of every experiment are in `../results/`:

| File | Contents |
|---|---|
| `main_results.csv` | All mechanisms at 60/80/100% EV ownership, all chargers smart, 2000 days (Table II) |
| `smart_share_sweep.csv` | Share of smart chargers 0-1 at 80% ownership, 1000 days (Fig. 4) |
| `penetration_sweep.csv` | EV ownership 20-100%, all chargers smart, 1000 days (Fig. 5) |
| `remedy_settings.csv` | Dither half-width, quota confidence and delay settings at 80/100% (Fig. 6) |
| `scheduler_sensitivity.csv` | Key comparison with the cheapest-first, commercial-style and mixed schedulers at 80/100% (Table II) |
| `fixed_point_history.csv` | Every round of every surcharge fixed point (supplementary figure S1) |
| `mean_ev_profile_p80.csv` | Mean one-minute EV load per mechanism at 80% (Fig. 3) |
| `example_day_ev_p80.csv` | Household load and one-minute EV load on the highest-household-load day in the sample (Fig. 1) |

Metric columns: `p_overload_pct` (days with a half-hourly peak above the firm
limit), `cvar95_peak30_kw` (mean of the worst 5% of daily peaks),
`max_switch_on_chargers` (most chargers switching on in the same minute, daily
mean), `unserved_pct` (energy not delivered by departure), `price_paid_p_kwh`
(average price paid), and `p_overload_min/max` (range across the last 10
fixed-point rounds, for surcharge tariffs).
