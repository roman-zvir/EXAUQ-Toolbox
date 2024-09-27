# Training a Gaussian Process Emulator

The purpose of this tutorial is to demonstrate how to train a Gaussian process (GP) to
emulate a simulator. It introduces the main objects that the EXAUQ-Toolbox provides for
training emulators and working with experimental designs. This tutorial will show you how
to:

* Work with simulator inputs and simulator domains.
* Create an experimental design, using Latin hypercube sampling provided by
  [scipy](https://scipy.org/).
* Define a Gaussian process and train it using simulator outputs for the experimental
  design.
* Make new predictions of simulator outputs using the trained GP.

!!! note

    Due to the pseudo-stochastic nature of the algorithms for fitting
    Gaussian processes, you may get slight differences in some of the code outputs in
    this tutorial.

## Simulator domain and inputs

From an abstract, mathematical point of view, we view a **simulator** as nothing more than
a (computationally laborious) deterministic function that takes an input and returns a single
real number. In general, the input consists of a point in a multi-dimensional space called
the **simulator domain** (or just **domain**).

For this tutorial, we'll be using a normal Python function that will act as a toy
simulator. Its domain will be the rectangle $\mathcal{D}$ consisting of points $(x_1, x_2)$ where
$-1 \leq x_1 \leq 1$ and $1 \leq x_2 \leq 100$. (In practice, a real simulator would most
likely run on a different computer with powerful performance capabilities — perhaps even
exascale levels of computational power — and the domain will likely have quite a few more dimensions.)

We begin by creating the domain of the simulator to represent the above rectangle. We
do this by using the [`SimulatorDomain`][exauq.core.modelling.SimulatorDomain] class,
like so:


``` { .python .copy }
from exauq.core.modelling import SimulatorDomain

# The bounds define the lower and upper bounds on each coordinate
bounds = [(-1, 1), (1, 100)]
domain = SimulatorDomain(bounds)
```

The dimension of the domain, i.e. the number of coordinates defining it, can be obtained
using the [`dim`][exauq.core.modelling.SimulatorDomain.dim] property:


``` { .python .copy }
print("Dimension of domain:", domain.dim)
```

<div class="result" markdown>
    Dimension of domain: 2
</div>


To represent the inputs to the simulator, the EXAUQ-Toolbox uses objects called
[`Input`][exauq.core.modelling.Input]s, which behave much like ordinary tuples of numbers.
We can create [`Input`][exauq.core.modelling.Input] objects like so:


``` { .python .copy }
from exauq.core.modelling import Input

x1 = Input(0, 99)  # i.e. (0, 99)
x2 = Input(1, 0)  # i.e. (1, 0)
```

[`Input`][exauq.core.modelling.Input]s behave like `tuple`s, in that we can get their
length (i.e. the dimension of the input point) and access the individual coordinates using
Python's (0-based) indexing.


``` { .python .copy }
print("Dimension of x1:", len(x1))
print("First coordinate of x1:", x1[0])
print("Second coordinate of x1:", x1[1])
```

<div class="result" markdown>
    Dimension of x1: 2
    First coordinate of x1: 0
    Second coordinate of x1: 99
</div>


We can also verify whether an [`Input`][exauq.core.modelling.Input] belongs to a simulator
domain using the [`in`][exauq.core.modelling.SimulatorDomain.__contains__] operator:


``` { .python .copy }
print(x1 in domain)  # x1 is contained in the domain
print(x2 in domain)  # x2 is not contained in the domain
```

<div class="result" markdown>
    True
    False
</div>


We now define our toy simulator function to be the mathematical function
$$
f(x_1, x_2) = x_2 + x_1^2 + x_2^2 - \sqrt{2} + \mathrm{sin}(2\pi x_1) + \mathrm{sin}(4\pi x_1 x_2)
$$
In code, this is given as follows:


``` { .python .copy }
import numpy as np

def sim_func(x: Input) -> float:
    return (
        x[1] + x[0]**2 + x[1]**2 - np.sqrt(2)
        + np.sin(2 * np.pi * x[0]) + np.sin(4 * np.pi * x[0] * x[1])
    )
```

## Creating an experimental design

We'll now go on to create a one-shot experimental design for this simulator, using the Latin hypercube method. The following wrapper function [`oneshot_lhs`][exauq.core.designers.oneshot_lhs] uses functionality provided by [scipy](https://scipy.org/) to create a Latin hypercube sample of 20 new input points.


``` { .python .copy }
from exauq.core.designers import oneshot_lhs

# Use the dimension of the domain in defining the Latin hypercube sampler.
# Also set a seed to make the sampling repeatable.
lhs_inputs = oneshot_lhs(domain = domain, 
                         batch_size = 20, 
                         seed = 1)
```

Behind the scenes in [`oneshot_lhs`][exauq.core.designers.oneshot_lhs], SciPy generates a Numpy array of shape (20, 2), where each value lies between 0 and 1. To integrate this design into the EXAUQ-Toolbox, the array is transformed into a sequence of [`Input`][exauq.core.modelling.Input] objects using the [`scale`][exauq.core.modelling.SimulatorDomain.scale] method.

This defines our one-shot experimental design. Next let's go on to train a Gaussian process emulator with this design.

## Training a GP

The EXAUQ-Toolbox provides an implementation of Gaussian processes via the
[`MogpEmulator`][exauq.core.emulators.MogpEmulator] class. This is based on the
[mogp_emulator](https://mogp-emulator.readthedocs.io/en/latest/index.html) package, but
provides a simpler interface. Furthermore, the
[`MogpEmulator`][exauq.core.emulators.MogpEmulator] class implicitly assumes a
zero mean function. We'll create a GP that uses a Matern 5/2 kernel function. (The
messages printed are from the `mogp_emulator` package and can be ignored: they arise
because the GP hasn't yet been trained on any data.)


``` { .python .copy }
from exauq.core.emulators import MogpEmulator

gp = MogpEmulator(kernel="Matern52")
```

<div class="result" markdown>
    Too few unique inputs; defaulting to flat priors
    Too few unique inputs; defaulting to flat priors
</div>


The [`training_data`][exauq.core.emulators.MogpEmulator.training_data] property of
[`MogpEmulator`][exauq.core.emulators.MogpEmulator]
objects returns a tuple of the data that the GP has been trained on, if at all. We can
verify that our GP hasn't yet been trained on any data, as evidenced by the empty tuple:


``` { .python .copy }
gp.training_data
```




<div class="result" markdown>
    ()
</div>



In order to train a GP, we need not just the experimental design that we created earlier
but also the simulator outputs for the inputs in the design. The inputs and corresponding
outputs need to be combined to create a sequence of
[`TrainingDatum`][exauq.core.modelling.TrainingDatum] objects, which will be fed into the
GP to train it. The following code first calculates the simulator outputs for the design
inputs, then creates a list of training data:


``` { .python .copy }
from exauq.core.modelling import TrainingDatum

# Calculate simulator outputs using our toy simulator function
outputs = [sim_func(x) for x in lhs_inputs]

# Create the training data of input/output pairs
data = [TrainingDatum(x, y) for x, y in zip(lhs_inputs, outputs)]

# Inspect the first datum in the list
data[0]
```




<div class="result" markdown>
    TrainingDatum(input=Input(np.float64(-0.45118216247002574), np.float64(75.49520470318662)), output=np.float64(5772.805093637131))
</div>



To train our GP, we use the [`fit`][exauq.core.emulators.MogpEmulator.fit] method with the
training data:


``` { .python .copy }
gp.fit(data)

# Verify training by examining the training data
assert len(gp.training_data) == 20
```

We have used our Latin hypercube design and the corresponding simulator outputs to train
our GP, making it ready to emulate our simulator. We put this to work in the next section.

## Making predictions with the GP

To finish off, let's use our newly-trained GP to estimate the output of our simulator at a
new input. We make a prediction with the GP using the
[`predict`][exauq.core.emulators.MogpEmulator.predict] method. Predictions from emulators
come with both the actual estimate and a measure of the uncertainty of that estimate. For
GPs, this is packaged up in a
[`GaussianProcessPrediction`][exauq.core.modelling.GaussianProcessPrediction] object,
which provides the [`estimate`][exauq.core.modelling.GaussianProcessPrediction.estimate]
property for the point estimate and the
[`variance`][exauq.core.modelling.GaussianProcessPrediction.variance] and
[`standard_deviation`][exauq.core.modelling.GaussianProcessPrediction.standard_deviation]
properties for a measure of the uncertainty (as the predictive variance and standard
deviation, respectively).


``` { .python .copy }
x = Input(0.5, 50)
prediction = gp.predict(x)

print(prediction)
print("Point estimate:", prediction.estimate)
print("Variance of estimate:", prediction.variance)
print("Standard deviation of estimate:", prediction.standard_deviation)
```

<div class="result" markdown>
    GaussianProcessPrediction(estimate=np.float64(2549.606787264347), variance=np.float64(2.521427646279335), standard_deviation=1.5879003892811838)
    Point estimate: 2549.606787264347
    Variance of estimate: 2.521427646279335
    Standard deviation of estimate: 1.5879003892811838
</div>


Let's see how well the prediction did against the true simulator value:


``` { .python .copy }
y = sim_func(x)  # the true value
pct_error = 100 * abs((prediction.estimate - y) / y)

print("Predicted value:", prediction.estimate)
print("Actual simulator value:", y)
print("Percentage error:", pct_error)
```

<div class="result" markdown>
    Predicted value: 2549.606787264347
    Actual simulator value: 2548.835786437627
    Percentage error: 0.03024913691272134
</div>


Finally, because the prediction comes from a GP, we can also calculate the normalised
expected square error via the
[`nes_error`][exauq.core.modelling.GaussianProcessPrediction.nes_error], which gives a
measure of the (absolute, squared) error that accounts for the uncertainty in the
prediction:


``` { .python .copy }
prediction.nes_error(y)
```




<div class="result" markdown>
    0.7203371924276764
</div>

