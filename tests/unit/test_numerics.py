import itertools
import math
import unittest

from exauq.core.numerics import FLOAT_TOLERANCE, equal_to_tolerance
from tests.utilities.utilities import make_window


class TestEqualToTolerance(unittest.TestCase):
    def assertAgreeOnRange(self, func1, func2, _range):
        for x in _range:
            self.assertIs(func1(x), func2(x))

    def test_equal_to_math_isclose_relative_tolerances(self):
        """Test that whether two reals are equal up to a relative tolerance agrees with
        the calculation given by math.isclose."""

        for x, rel_tol in itertools.product([-1, 1], [1e-1, 1e-2, 1e-3]):
            with self.subTest(x=x, rel_tol=rel_tol):
                # Note: use of abs_tol=0 forces the use of the relative tolerance
                self.assertAgreeOnRange(
                    lambda y: equal_to_tolerance(x, y, rel_tol=rel_tol, abs_tol=0),
                    lambda y: math.isclose(x, y, rel_tol=rel_tol, abs_tol=0),
                    _range=make_window(x, 2 * rel_tol, type="rel"),
                )

    def test_equal_to_math_isclose_absolute_tolerances(self):
        """Test that whether two reals are equal up to an absolute tolerance agrees with
        the calculation given by math.isclose."""

        for x, abs_tol in itertools.product([-0.1, 0, 0.1], [0.1, 0.05, 0.01]):
            with self.subTest(x=x, abs_tol=abs_tol):
                # Note: use of rel_tol=0 forces the use of the absolute tolerance
                self.assertAgreeOnRange(
                    lambda y: equal_to_tolerance(x, y, rel_tol=0, abs_tol=abs_tol),
                    lambda y: math.isclose(x, y, rel_tol=0, abs_tol=abs_tol),
                    _range=make_window(x, 2 * abs_tol),
                )

    def test_default_tolerances(self):
        """Test that the default tolerance used for both relative and absolute tolerances
        is equal to the package's float tolerance constant."""

        # Relative tolerance case
        for x in [-1, 1]:
            with self.subTest(x=x):
                self.assertAgreeOnRange(
                    lambda y: equal_to_tolerance(x, y),
                    lambda y: math.isclose(
                        x, y, rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE
                    ),
                    _range=make_window(x, 2 * FLOAT_TOLERANCE, type="rel"),
                )

        # Absolute tolerance case
        self.assertAgreeOnRange(
            lambda y: equal_to_tolerance(x, y),
            lambda y: math.isclose(
                x, y, rel_tol=FLOAT_TOLERANCE, abs_tol=FLOAT_TOLERANCE
            ),
            _range=make_window(x, 2 * FLOAT_TOLERANCE),
        )


if __name__ == "__main__":
    unittest.main()
