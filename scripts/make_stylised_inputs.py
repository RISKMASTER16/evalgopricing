"""Write the stylised household-load and wholesale-price shapes to data/inputs/.

Replace these CSVs with measured data and rerun the experiments to use real profiles.
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data" / "inputs"
HOURS = np.arange(48) * 0.5 + 0.25  # slot centres


def bump(h, centre, width, height):
    # circular Gaussian bump on a 24 h clock
    d = np.minimum(np.abs(h - centre), 24 - np.abs(h - centre))
    return height * np.exp(-0.5 * (d / width) ** 2)


def background(peak_kw=72.0):
    shape = (0.30
             + bump(HOURS, 8.0, 1.2, 0.25)    # morning
             + bump(HOURS, 13.0, 2.5, 0.12)   # midday
             + bump(HOURS, 18.25, 1.8, 0.70)  # evening peak
             + bump(HOURS, 21.5, 1.5, 0.15))  # late evening
    return shape / shape.max() * peak_kw


def wholesale_shape():
    shape = (0.75
             + bump(HOURS, 8.0, 1.5, 0.30)
             - bump(HOURS, 13.5, 2.0, 0.10)   # solar dip
             + bump(HOURS, 18.0, 1.5, 0.75))
    return shape / shape.mean()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    slot = np.arange(48)
    start = [f"{int(s // 2):02d}:{30 * (s % 2):02d}" for s in slot]
    pd.DataFrame({"slot": slot, "start": start,
                  "background_kw": background().round(3)}).to_csv(
        OUT / "background_profile.csv", index=False)
    pd.DataFrame({"slot": slot, "start": start,
                  "wholesale_shape": wholesale_shape().round(4)}).to_csv(
        OUT / "wholesale_shape.csv", index=False)
    pd.DataFrame({"component": ["overnight timers", "daytime", "evening return"],
                  "weight": [0.04, 0.30, 0.66],
                  "mean_h": [0.5, 10.0, 18.5],
                  "sd_h": [0.4, 2.4, 3.6]}).to_csv(
        OUT / "plugin_mixture.csv", index=False)
    print("wrote", sorted(p.name for p in OUT.glob("*.csv")))


if __name__ == "__main__":
    main()
