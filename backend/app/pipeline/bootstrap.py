"""
bootstrap.py — Bootstrap confidence interval computation.

Parameters are taken from settings (BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
so they are always displayed next to the interval in the UI.
"""

from __future__ import annotations

import random
from typing import Callable, Optional

from ..config import settings


def bootstrap_ci(
    data: list,
    metric_fn: Callable[[list], Optional[float]],
    alpha: float = 0.05,
) -> tuple[Optional[float], Optional[float]]:
    """
    Compute a (1-alpha) bootstrap confidence interval for metric_fn over data.

    Parameters
    ----------
    data      : List of items (RunResult, layer1 JSON strings, etc.)
    metric_fn : Function mapping a list of items to a float (or None).
    alpha     : Significance level (default 0.05 → 95% CI).

    Returns
    -------
    (ci_low, ci_high) or (None, None) if not enough data.
    """
    n = len(data)
    if n < 2:
        return None, None

    rng = random.Random(settings.bootstrap_seed)
    samples: list[float] = []

    for _ in range(settings.bootstrap_resamples):
        resample = [data[rng.randint(0, n - 1)] for _ in range(n)]
        val = metric_fn(resample)
        if val is not None:
            samples.append(val)

    if len(samples) < 10:
        return None, None

    samples.sort()
    lo = int(alpha / 2 * len(samples))
    hi = int((1 - alpha / 2) * len(samples))
    return round(samples[lo], 4), round(samples[min(hi, len(samples) - 1)], 4)
