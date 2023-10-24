"""Functions etc. to support testing"""

from numbers import Real
from typing import Literal

import numpy as np


def exact(string: str):
    """Turn a string into a regular expressions that defines an exact match on the
    string.
    """
    escaped = string
    for char in ["\\", "(", ")"]:
        escaped = escaped.replace(char, _escape(char))

    return "^" + escaped + "$"


def _escape(char):
    return "\\" + char


def make_window(x: Real, tol: float, type: Literal["abs", "rel"] = "abs", num: int = 50):
    """Make a range of numbers around a number with boundaries defined by a tolerance.

    This function is useful for generating ranges of numbers that will form part of a
    test for numerical equality up to some tolerance.

    If `type` is equal to ``'abs'``, then the range returned will be `num` equally-spaced
    numbers between ``x - tol`` and ``x + tol``. If `type` is ``'rel'``, then the range
    will be `num` (linearly) equally-spaced numbers between ``(1 - tol) * x`` and
    ``x / (1 - tol)``.
    """

    if type == "abs":
        return np.linspace(x - tol, x + tol, num=num)
    elif type == "rel":
        return np.linspace(x * (1 - tol), x / (1 - tol), num=num)
    else:
        raise ValueError("'type' must equal one of 'abs' or 'rel'")
