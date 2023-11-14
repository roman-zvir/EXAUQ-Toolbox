import math
import unittest
import unittest.mock

import mogp_emulator as mogp
import numpy as np
from mogp_emulator.GPParams import GPParams

from exauq.core.emulators import MogpEmulator, MogpHyperparameters
from exauq.core.modelling import Input, Prediction, TrainingDatum
from exauq.core.numerics import equal_within_tolerance
from tests.utilities.utilities import exact


class TestMogpEmulator(unittest.TestCase):
    def setUp(self) -> None:
        # Some default args to use for constructing mogp GaussianProcess objects
        self.inputs = np.array([[0, 0], [0.2, 0.1]])
        self.targets = np.array([1, 2])

        # kwargs for constructing an mogp GuassianProcess object
        self.gp_kwargs = {
            "mean": None,
            "kernel": "Matern52",  # non-default
            "priors": None,
            "nugget": "pivot",  # non-default
            "inputdict": {},
            "use_patsy": False,  # non-default
        }

        # Default training data for fitting an emulator
        self.training_data = [
            TrainingDatum(Input(0, 0), 1),
            TrainingDatum(Input(0.2, 0.1), 2),
            TrainingDatum(Input(0.3, 0.5), 3),
            TrainingDatum(Input(0.7, 0.4), 4),
            TrainingDatum(Input(0.9, 0.8), 5),
        ]

        # Input not contained in training data, for making predictions
        self.x = Input(0.1, 0.1)

    def assertAlmostBetween(self, x, lower, upper, **kwargs) -> None:
        """Checks whether a number lies between bounds up to a tolerance.

        An AssertionError is thrown unless `lower` < `x` < `upper` or `x` is
        close to either bound. Keyword arguments are passed to the function
        `math.isclose`, with `rel_tol` and `abs_tol` being used to define the
        tolerances in the closeness check (see the documentation for
        `math.isclose` on their definition and default values).
        """
        almost_between = (
            (lower < x < upper)
            or math.isclose(x, lower, **kwargs)
            or math.isclose(x, upper, **kwargs)
        )
        assert almost_between, "'x' not between lower and upper bounds to given tolerance"

    def test_initialiser(self):
        """Test that an instance of MogpEmulator can be initialised from args
        and kwargs required of an mogp GaussianProcess object.
        """

        MogpEmulator(**self.gp_kwargs)

    def test_initialiser_error(self):
        """Test that a RuntimeError is raised if a mogp GaussianProcess
        couldn't be initialised.
        """

        with self.assertRaises(RuntimeError) as cm:
            MogpEmulator(men=None)

        expected_msg = (
            "Could not construct mogp-emulator GaussianProcess "
            "during initialisation of MogpEmulator"
        )
        self.assertEqual(expected_msg, str(cm.exception))

    @unittest.mock.patch("exauq.core.emulators.GaussianProcess")
    def test_initialiser_base_exception_bubbled(self, mock):
        """Test that an exception that isn't derived from Exception gets raised as-is."""

        mock.side_effect = BaseException("msg")
        with self.assertRaises(BaseException) as cm:
            MogpEmulator()

        self.assertEqual("msg", str(cm.exception))

    def test_underlying_gp_kwargs(self):
        """Test that the underlying mogp GaussianProcess was constructed with
        kwargs supplied to the MogpEmulator initialiser."""

        # Non-default choices for some kwargs
        emulator = MogpEmulator(
            kernel=self.gp_kwargs["kernel"], nugget=self.gp_kwargs["nugget"]
        )

        self.assertEqual("Matern 5/2 Kernel", str(emulator.gp.kernel))
        self.assertEqual(self.gp_kwargs["nugget"], emulator.gp.nugget_type)

    def test_initialiser_inputs_targets_ignored(self):
        """Test that inputs and targets kwargs are ignored when initialising
        an emulator."""

        emulator = MogpEmulator(inputs=self.inputs, targets=self.targets)
        self.assertEqual(0, emulator.gp.inputs.size)
        self.assertEqual(0, emulator.gp.targets.size)

    def test_training_data(self):
        """Test that the training data in the underlying GP and the
        training_data property is empty when an emulator is constructed."""

        emulator = MogpEmulator()
        self.assertEqual(0, emulator.gp.inputs.size)
        self.assertEqual(0, emulator.gp.targets.size)
        self.assertEqual([], emulator.training_data)

    def test_fit_no_training_data(self):
        """Test that fitting the emulator results in the underlying GP being fit
        with hyperparameter estimation."""

        inputs = np.array([[0, 0], [0.2, 0.1], [0.3, 0.5], [0.7, 0.4], [0.9, 0.8]])
        targets = np.array([1, 2, 3.1, 9, 2])
        gp = mogp.fit_GP_MAP(mogp.GaussianProcess(inputs, targets))
        emulator = MogpEmulator()
        emulator.fit(TrainingDatum.list_from_arrays(inputs, targets))

        # Note: need to use allclose because fitting is not deterministic.
        self.assertTrue(
            np.allclose(gp.theta.corr, emulator.gp.theta.corr, rtol=1e-5, atol=0)
        )
        self.assertTrue(
            np.allclose(gp.theta.cov, emulator.gp.theta.cov, rtol=1e-5, atol=0)
        )
        self.assertTrue(
            np.allclose(gp.theta.nugget, emulator.gp.theta.nugget, rtol=1e-5, atol=0)
        )

    def test_fit_bounds_converts_to_raw(self):
        """Test that bounds on correlation length parameters and the covariance
        are transformed to bounds on raw parameters when fitting. For the
        transformations, see:
        https://mogp-emulator.readthedocs.io/en/latest/implementation/GPParams.html#mogp_emulator.GPParams.GPParams
        """

        mock = unittest.mock.MagicMock()
        with unittest.mock.patch("exauq.core.emulators.fit_GP_MAP", mock):
            bounds = (
                (1, math.e),  # correlation = exp(-0.5 * raw_corr)
                (math.exp(-2), math.exp(3)),  # correlation = exp(-0.5 * raw_corr)
                (1, math.e),  # covariance
            )
            emulator = MogpEmulator()
            emulator.fit(self.training_data, hyperparameter_bounds=bounds)

            # Check that the underlying fitting function was called with correct
            # bounds
            raw_bounds = (
                (-2.0, 0.0),  # raw correlation = -2 * log(corr)
                (-6.0, 4.0),  # raw correlation
                (0.0, 1.0),  # raw covariance = log(cov)
            )
            self.assertEqual(raw_bounds, mock.call_args.kwargs["bounds"])

    def test_fit_bounds_none(self):
        """Test that None entries for bounds are converted to None entries when
        fitting."""

        mock = unittest.mock.MagicMock()
        with unittest.mock.patch("exauq.core.emulators.fit_GP_MAP", mock):
            bounds = ((1, None), (None, 1))
            emulator = MogpEmulator()
            emulator.fit(self.training_data, hyperparameter_bounds=bounds)

            # Check that the underlying fitting function was called with correct
            # bounds
            raw_bounds = ((None, 0.0), (None, 0.0))
            self.assertEqual(raw_bounds, mock.call_args.kwargs["bounds"])

    def test_compute_raw_param_bounds_non_positive(self):
        """Test that non-positive lower bounds are converted to None when
        fitting."""

        mock = unittest.mock.MagicMock()
        with unittest.mock.patch("exauq.core.emulators.fit_GP_MAP", mock):
            bounds = ((-np.inf, 1), (0, 1), (-math.e, 1))
            emulator = MogpEmulator()
            emulator.fit(self.training_data, hyperparameter_bounds=bounds)

            # Check that the underlying fitting function was called with correct
            # bounds
            raw_bounds = ((0.0, None), (0.0, None), (None, 0.0))
            self.assertEqual(raw_bounds, mock.call_args.kwargs["bounds"])

    def test_fit_training_data(self):
        """Test that the emulator is trained on the supplied training data
        and its training_data property is updated."""

        inputs = np.array([[0, 0], [0.2, 0.1], [0.3, 0.5], [0.7, 0.4], [0.9, 0.8]])
        targets = np.array([1, 2, 3.1, 9, 2])
        emulator = MogpEmulator()
        training_data = TrainingDatum.list_from_arrays(inputs, targets)
        emulator.fit(training_data)

        self.assertTrue(np.allclose(inputs, emulator.gp.inputs))
        self.assertTrue(np.allclose(targets, emulator.gp.targets))
        self.assertEqual(training_data, emulator.training_data)

    def test_fit_with_bounds_error(self):
        """Test that a ValueError is raised if a non-positive value is supplied for
        one of the upper bounds."""

        emulator = MogpEmulator()
        training_data = [TrainingDatum(Input(0.5), 0.5)]

        with self.assertRaises(ValueError) as cm:
            emulator.fit(training_data, hyperparameter_bounds=[(None, -1)])

        expected_msg = "Upper bounds must be positive numbers"
        self.assertEqual(expected_msg, str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            emulator.fit(training_data, hyperparameter_bounds=[(None, 0)])

        expected_msg = "Upper bounds must be positive numbers"
        self.assertEqual(expected_msg, str(cm.exception))

    def test_fit_with_bounds(self):
        """Test that fitting the emulator respects bounds on hyperparameters
        when these are supplied."""

        inputs = np.array([[0, 0], [0.2, 0.1], [0.3, 0.5], [0.7, 0.4], [0.9, 0.8]])
        targets = np.array([1, 2, 3.1, 9, 2])
        gp = mogp.fit_GP_MAP(mogp.GaussianProcess(inputs, targets))

        # Compute bounds to apply, by creating small windows away from known
        # optimal values of the hyperparameters.
        corr = gp.theta.corr
        cov = gp.theta.cov
        bounds = (
            (0.8 * corr[0], 0.9 * corr[0]),
            (0.8 * corr[1], 0.9 * corr[1]),
            (1.1 * cov, 1.2 * cov),
        )

        emulator = MogpEmulator()
        emulator.fit(
            TrainingDatum.list_from_arrays(inputs, targets),
            hyperparameter_bounds=bounds,
        )
        actual_corr = emulator.gp.theta.corr
        actual_cov = emulator.gp.theta.cov

        # Note: need to check values are between bounds up to a tolerance
        # due to floating point inprecision.
        self.assertAlmostBetween(
            actual_corr[0], bounds[0][0], bounds[0][1], rel_tol=1e-10
        )
        self.assertAlmostBetween(
            actual_corr[1], bounds[1][0], bounds[1][1], rel_tol=1e-10
        )
        self.assertAlmostBetween(actual_cov, bounds[2][0], bounds[2][1], rel_tol=1e-10)

    def test_fit_gp_kwargs(self):
        """Test that, after fitting, the underlying mogp emulator has the same
        kwarg settings as the original did before fitting."""

        emulator = MogpEmulator(nugget=self.gp_kwargs["nugget"])

        emulator.fit(training_data=self.training_data)

        self.assertEqual(self.gp_kwargs["nugget"], emulator.gp.nugget_type)

    def test_fit_ignores_inputs_targets(self):
        """Test that fitting ignores any inputs and targets supplied during
        initialisation of the emulator."""

        emulator = MogpEmulator(inputs=self.inputs, targets=self.targets)
        emulator.fit([])

        self.assertEqual(0, emulator.gp.inputs.size)
        self.assertEqual(0, emulator.gp.targets.size)
        self.assertEqual([], emulator.training_data)

    def test_fit_empty_training_data(self):
        """Test that the training data and underlying mogp GaussianProcess
        are not changed when fitting with no training data."""

        # Case where no data has previously been fit
        emulator = MogpEmulator()

        emulator.fit([])

        self.assertEqual(0, emulator.gp.inputs.size)
        self.assertEqual(0, emulator.gp.targets.size)
        self.assertEqual([], emulator.training_data)

        # Case where data has previously been fit
        inputs = np.array([[0, 0], [0.2, 0.1], [0.3, 0.5], [0.7, 0.4], [0.9, 0.8]])
        targets = np.array([1, 2, 3.1, 9, 2])
        emulator.fit(TrainingDatum.list_from_arrays(inputs, targets))
        expected_inputs = emulator.gp.inputs
        expected_targets = emulator.gp.targets
        expected_training_data = emulator.training_data

        emulator.fit([])

        self.assertTrue(np.allclose(expected_inputs, emulator.gp.inputs))
        self.assertTrue(np.allclose(expected_targets, emulator.gp.targets))
        self.assertEqual(expected_training_data, emulator.training_data)

    def test_fitted_hyperparameters_can_be_retrieved(self):
        """Given an emulator, when it is fit to training data then the fitted
        hyperparameters can be retrieved and agree with those in the underlying
        MOGP GaussianProcess object."""

        emulator = MogpEmulator()
        emulator.fit(self.training_data)
        self.assertEqual(
            MogpHyperparameters.from_mogp_gp(emulator.gp), emulator.fit_hyperparameters
        )

    def test_fit_with_given_hyperparameters_with_fixed_nugget(self):
        """Given an emulator and a set of hyperparameters that includes a value for the
        nugget, when the emulator is fit with the hyperparameters then these are used to
        train the underlying MOGP GaussianProcess object."""

        hyperparameters = MogpHyperparameters(corr=[0.5, 0.4], cov=2, nugget=1.0)
        for nugget in [2.0, "adaptive", "fit", "pivot"]:
            with self.subTest(nugget=nugget):
                emulator = MogpEmulator(nugget=nugget)
                emulator.fit(self.training_data, hyperparameters=hyperparameters)
                self.assertEqual(hyperparameters, emulator.fit_hyperparameters)
                self.assertEqual(
                    MogpHyperparameters.from_mogp_gp(emulator.gp), hyperparameters
                )

    def test_fit_with_given_hyperparameters_without_fixed_nugget(self):
        """Given an emulator and a set of hyperparameters that doesn't include a value for
        the nugget, when the emulator is fit with the hyperparameters then these are used
        to train the underlying MOGP GaussianProcess object and the nugget is determined
        as per the settings supplied when creating the emulator."""

        hyperparameters = MogpHyperparameters(corr=[0.5, 0.4], cov=2)
        float_val = 1.0
        for nugget in [float_val, "adaptive", "pivot"]:
            with self.subTest(nugget=nugget):
                emulator = MogpEmulator(nugget=nugget)
                emulator.fit(self.training_data, hyperparameters=hyperparameters)

                # Check the fitted hyperparameters are as calculated from MOGP
                hyperparameters_gp = MogpHyperparameters.from_mogp_gp(emulator.gp)

                # Check the correlation length parameters and covariance agree with those
                # supplied for fitting.
                self.assertEqual(hyperparameters_gp, emulator.fit_hyperparameters)
                self.assertTrue(
                    equal_within_tolerance(
                        hyperparameters.corr, emulator.fit_hyperparameters.corr
                    )
                )
                self.assertTrue(
                    equal_within_tolerance(
                        hyperparameters.cov, emulator.fit_hyperparameters.cov
                    )
                )

                # Check nugget used in fitting agrees with the specific value supplied at
                # emulator creation, if relevant.
                if nugget == float_val:
                    self.assertTrue(
                        equal_within_tolerance(
                            nugget, emulator.fit_hyperparameters.nugget
                        )
                    )

    def test_fit_with_given_hyperparameters_missing_nugget_error(self):
        """Given an emulator where the nugget is to be estimated (via the 'fit' value in
        MOGP), raise a ValueError if one attempts to fit the emulator with specific
        hyperparameters that don't include a nugget."""

        emulator = MogpEmulator(nugget="fit")
        hyperparameters = MogpHyperparameters(corr=[0.5, 0.4], cov=2)
        with self.assertRaisesRegex(
            ValueError,
            exact(
                "The underlying MOGP GaussianProcess was created with 'nugget'='fit', but "
                "the nugget supplied during fitting is "
                f"{hyperparameters.nugget}, when it should instead be a float."
            ),
        ):
            emulator.fit(self.training_data, hyperparameters=hyperparameters)

    def test_predict_returns_prediction_object(self):
        """Given a trained emulator, check that predict() returns a Prediction object."""

        emulator = MogpEmulator()
        emulator.fit(self.training_data)

        self.assertIsInstance(emulator.predict(self.x), Prediction)

    def test_predict_non_input_error(self):
        """Given an emulator, test that a TypeError is raised when trying to predict on
        an object not of type Input."""

        emulator = MogpEmulator()

        for x in [0.5, None, "0.5"]:
            with self.subTest(x=x), self.assertRaisesRegex(
                TypeError,
                exact(f"Expected 'x' to be of type Input, but received {type(x)}."),
            ):
                emulator.predict(x)

    def test_predict_not_trained_error(self):
        """Given an emulator that hasn't been trained on data, test that an
        AssertionError is raised when using the emulator to make a prediction."""

        emulator = MogpEmulator()

        with self.assertRaisesRegex(
            RuntimeError,
            exact(
                "Cannot make prediction because emulator has not been trained on any data."
            ),
        ):
            emulator.predict(self.x)

    def test_predict_input_wrong_dim_error(self):
        """Given a trained emulator, test that a ValueError is raised if the dimension
        of the input is not the same as for the training data."""

        emulator = MogpEmulator()
        emulator.fit(self.training_data)
        expected_dim = len(self.training_data[0].input)

        for x in [Input(), Input(0.5), Input(0.5, 0.5, 0.5)]:
            with self.subTest(x=x), self.assertRaisesRegex(
                ValueError,
                exact(
                    f"Expected 'x' to be an Input with {expected_dim} coordinates, but "
                    f"it has {len(x)} instead."
                ),
            ):
                emulator.predict(x)

    def test_predict_training_data_points(self):
        """Given an emulator trained on data, test that the training data inputs are
        predicted exactly with no uncertainty."""

        emulator = MogpEmulator()
        emulator.fit(self.training_data)
        for datum in self.training_data:
            self.assertEqual(
                Prediction(estimate=datum.output, variance=0),
                emulator.predict(datum.input),
            )

    def test_predict_away_training_data_points(self):
        """Given an emulator trained on data, test that predictions away from the data
        inputs have uncertainty."""

        emulator = MogpEmulator()
        emulator.fit(self.training_data)

        # Note: use list in the following because Inputs aren't hashable
        training_inputs = [datum.input for datum in self.training_data]

        for x in (Input(0.1 * n, 0.1 * n) for n in range(1, 10)):
            assert x not in training_inputs
            self.assertTrue(emulator.predict(x).variance > 0)


class TestMogpHyperparameters(unittest.TestCase):
    def test_transform_corr_is_minus_2log_corr(self):
        """The transformed correlation is equal to `-2 * log(corr)`."""

        positive_reals = [0.1, 1, 10, np.float16(1.1)]
        for corr in positive_reals:
            self.assertEqual(
                -2 * math.log(corr), MogpHyperparameters.transform_corr(corr)
            )

    def test_transform_corr_non_real_arg_raises_type_error(self):
        "A TypeError is raised if the argument supplied is not a real number."

        # N.B. although single-element Numpy arrays can be converted to scalars this is
        # deprecated functionality and will throw an error in the future.

        nonreal_objects = [2j, "1", np.array([2])]
        for corr in nonreal_objects:
            with self.subTest(corr=corr), self.assertRaisesRegex(
                TypeError,
                exact(f"Expected 'corr' to be a real number, but received {type(corr)}."),
            ):
                _ = MogpHyperparameters.transform_corr(corr)

    def test_transform_corr_with_nonpositive_value_raises_value_error(self):
        "A ValueError is raised if the argument supplied is not > 0."

        nonpositive_reals = [-0.5, 0]
        for corr in nonpositive_reals:
            with self.assertRaisesRegex(
                ValueError,
                exact(f"'corr' must be a positive real number, but received {corr}."),
            ):
                _ = MogpHyperparameters.transform_corr(corr)


if __name__ == "__main__":
    unittest.main()
