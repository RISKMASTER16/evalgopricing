"""Load model inputs from data/inputs/ into one parameter object."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "data" / "inputs"

MIN_PER_DAY = 1440
SLOT_MIN = 30
N_SLOTS = 48


@dataclass
class Inputs:
    p: dict                      # scalar parameters by name
    background: np.ndarray       # forecast non-EV load, kW, 48 slots
    wholesale_shape: np.ndarray  # normalised day-ahead shape, 48 slots
    mix_w: np.ndarray            # plug-in mixture weights
    mix_mu: np.ndarray           # plug-in mixture means, h
    mix_sd: np.ndarray           # plug-in mixture standard deviations, h

    def __getitem__(self, key):
        return self.p[key]


def load_inputs(path: Path = INPUTS) -> Inputs:
    prm = pd.read_csv(path / "parameters.csv")
    p = dict(zip(prm["name"], prm["value"].astype(float)))
    bg = pd.read_csv(path / "background_profile.csv")["background_kw"].to_numpy()
    ws = pd.read_csv(path / "wholesale_shape.csv")["wholesale_shape"].to_numpy()
    mix = pd.read_csv(path / "plugin_mixture.csv")
    return Inputs(p=p, background=bg.astype(float), wholesale_shape=ws.astype(float),
                  mix_w=mix["weight"].to_numpy(float),
                  mix_mu=mix["mean_h"].to_numpy(float),
                  mix_sd=mix["sd_h"].to_numpy(float))


def lognormal_from_mean_cv(mean, cv):
    """Return (mu, sigma) of a lognormal with the given mean and CV."""
    sigma = np.sqrt(np.log1p(cv ** 2))
    return np.log(mean) - sigma ** 2 / 2, sigma


def slot_to_minutes(x):
    """Repeat a 48-slot array to 1440 minutes."""
    return np.repeat(np.asarray(x, float), SLOT_MIN, axis=-1)
