# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/MonoDenseLayer.ipynb.

# %% auto 0
__all__ = ['get_saturated_activation', 'get_activation_functions', 'apply_activations', 'check_monotonicity_indicator_values',
           'apply_monotonicity_indicator_to_kernel', 'MonotonicDense']

# %% ../nbs/MonoDenseLayer.ipynb 2
from typing import *
from contextlib import contextmanager

import numpy as np
from numpy.typing import ArrayLike, NDArray

import tensorflow as tf
import tensorflow.keras.backend as K
from tensorflow.keras.layers import Dense

# %% ../nbs/MonoDenseLayer.ipynb 7
def get_saturated_activation(
    convex_activation: Callable[[tf.Tensor], tf.Tensor],
    concave_activation: Callable[[tf.Tensor], tf.Tensor],
    a: float = 1.0,
    c: float = 1.0,
) -> Callable[[tf.Tensor], tf.Tensor]:
    def saturated_activation(
        x: tf.Tensor,
        convex_activation: Callable[[tf.Tensor], tf.Tensor] = convex_activation,
        concave_activation: Callable[[tf.Tensor], tf.Tensor] = concave_activation,
        a: float = a,
        c: float = c,
    ) -> tf.Tensor:
        cc = convex_activation(tf.ones_like(x) * c)
        return a * tf.where(
            x <= c,
            convex_activation(x + c) - cc,
            concave_activation(x - c) + cc,
        )

    return saturated_activation

# %% ../nbs/MonoDenseLayer.ipynb 8
def get_activation_functions(
    activation: Optional[Union[str, Callable[[tf.Tensor], tf.Tensor]]] = None
) -> Tuple[
    Optional[Callable[[tf.Tensor], tf.Tensor]],
    Optional[Callable[[tf.Tensor], tf.Tensor]],
    Optional[Callable[[tf.Tensor], tf.Tensor]],
]:
    if activation:
        convex_activation = tf.keras.activations.get(
            activation.lower() if isinstance(activation, str) else activation
        )
        concave_activation = lambda x: -convex_activation(-x)
        saturated_activation = get_saturated_activation(
            convex_activation, concave_activation
        )
        return convex_activation, concave_activation, saturated_activation
    else:
        return None, None, None

# %% ../nbs/MonoDenseLayer.ipynb 10
def apply_activations(
    x: tf.Tensor,
    *,
    units,
    activation: Optional[Union[str, Callable[[tf.Tensor], tf.Tensor]]] = None,
    is_convex: bool = False,
    is_concave: bool = False,
    activation_weights: Tuple[float, float, float] = (1.0, 1.0, 1.0),
) -> tf.Tensor:
    (
        convex_activation,
        concave_activation,
        saturated_activation,
    ) = get_activation_functions(activation)

    if convex_activation is None:
        return x
    elif is_convex:
        return convex_activation(x)
    elif is_concave:
        return concave_activation(x)
    else:
        if len(activation_weights) != 3:
            raise ValueError(f"activation_weights={activation_weights}")
        if (np.array(activation_weights) < 0).any():
            raise ValueError(f"activation_weights={activation_weights}")
        normalized_activation_weights = np.array(activation_weights) / sum(
            activation_weights
        )

        convex_length = round(normalized_activation_weights[0] * units)
        concave_length = round(normalized_activation_weights[1] * units)
        saturated_length = units - convex_length - concave_length

        x_convex, x_concave, x_saturated = tf.split(
            x, (convex_length, concave_length, saturated_length), axis=-1
        )

        y_convex = convex_activation(x_convex)
        y_concave = convex_activation(x_concave)
        y_saturated = saturated_activation(x_saturated)

        y = tf.concat([y_convex, y_concave, y_saturated], axis=-1)

        return y

# %% ../nbs/MonoDenseLayer.ipynb 13
def check_monotonicity_indicator_values(
    monotonicity_indicator: Union[int, NDArray[np.int_]]
):
    if isinstance(monotonicity_indicator, int):
        if monotonicity_indicator not in [-1, 0, 1]:
            raise ValueError(
                f"monotonicity_indicator must be one of -1, 0, 1, but it is {monotonicity_indicator} instead!"
            )
    else:
        r = (
            (monotonicity_indicator == -1)
            | (monotonicity_indicator == 0)
            | (monotonicity_indicator == 1)
        )
        if not r.all():
            raise ValueError(
                f"Each element of monotonicity_indicator must be one of -1, 0, 1, but it is {monotonicity_indicator}!"
            )

# %% ../nbs/MonoDenseLayer.ipynb 15
def apply_monotonicity_indicator_to_kernel(
    kernel: tf.Variable, monotonicity_indicator: Union[int, NDArray[np.int_]]
) -> tf.Tensor:
    abs_kernel = tf.abs(kernel)
    if isinstance(monotonicity_indicator, int):
        if monotonicity_indicator == 1:
            return abs_kernel
        elif monotonicity_indicator == -1:
            return -abs_kernel
        else:
            return kernel
    else:
        if kernel.shape != monotonicity_indicator.shape:
            raise ValueError(
                "Kernel and monotonicity_indicator must have the same shapes, but we have {kernel.shape} != {monotonicity_indicator.shape=}"
            )
        #         monotonicity_indicator = np.expand_dims(monotonicity_indicator, axis=-1)
        kernel = tf.where(
            monotonicity_indicator == 1,
            abs_kernel,
            kernel,
        )
        return tf.where(monotonicity_indicator == -1, -abs_kernel, kernel)

# %% ../nbs/MonoDenseLayer.ipynb 19
class MonotonicDense(Dense):
    """Monotonic counterpart of the regular Dense Layer of tf.keras"""

    def __init__(
        self,
        units: int,
        *,
        activation: Optional[Union[str, Callable[[tf.Tensor], tf.Tensor]]] = None,
        monotonicity_indicator: Union[int, NDArray[np.int_]] = 1,
        is_convex: bool = False,
        is_concave: bool = False,
        activation_weights: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        **kwargs,
    ):
        """Constructs a new MonotonicDense instance.

        Params:
            units: Positive integer, dimensionality of the output space.
            activation: Activation function to use, it is assumed to be convex monotonically
                increasing function such as "relu" or "elu"
            monotonicity_indicator: Vector to indicate which of the inputs are monotonically increasing or
                monotonically decreasing or non-monotonic. Has value 1 for monotonically increasing,
                -1 for monotonically decreasing and 0 for non-monotonic.
            is_convex: convex if set to True
            is_concave: concave if set to True
            activation_weights: relative weights for each type of activation, the default is (1.0, 1.0, 1.0).
                Ignored if is_convex or is_concave is set to True
            **kwargs: passed directly to the constructor of `Dense`

        Returns:
            N-D tensor with shape: `(batch_size, ..., units)`.

        Raise:
            ValueError:
                - if both **is_concave** and **is_convex** are set to **True**, or
                - if any component of activation_weights is negative or there is not exactly three components
        """
        check_monotonicity_indicator_values(monotonicity_indicator)

        if is_convex and is_concave:
            raise ValueError(
                "The model cannot be set to be both convex and concave (only linear functions are both)."
            )

        if len(activation_weights) != 3:
            raise ValueError(
                f"There must be exactly three components of activation_weights, but we have this instead: {activation_weights}."
            )

        if (np.array(activation_weights) < 0).any():
            raise ValueError(
                f"Values of activation_weights must be non-negative, but we have this instead: {activation_weights}."
            )

        super(MonotonicDense, self).__init__(units, activation=None, **kwargs)

        self.units = units
        self.org_activation = activation
        self.activation_weights = activation_weights
        self.monotonicity_indicator = monotonicity_indicator
        self.is_convex = is_convex
        self.is_concave = is_concave

    @contextmanager
    def replace_kernel(self):
        """Replaces kernel with non-negative or non-positive values according
        to the **monotonicity_indicator**
        """
        kernel_org = self.kernel
        self.kernel = apply_monotonicity_indicator_to_kernel(
            self.kernel, self.monotonicity_indicator
        )
        try:
            yield
        finally:
            self.kernel = kernel_org

    def build(self, input_shape, *args, **kwargs):
        """Build

        Args:
            input_shape: input tensor
        """
        super(MonotonicDense, self).build(input_shape, *args, **kwargs)
        if not isinstance(self.monotonicity_indicator, int):
            if self.kernel.shape != self.monotonicity_indicator.shape:
                raise ValueError(
                    f"Input shape and monotonicity vector don't have matching shapes: {self.kernel.shape} != {self.monotonicity_indicator.shape}"
                )

    def call(self, inputs):
        """Call

        Args:
            inputs: input tensor
        """
        # calculate W'*x+y after we replace the kernal according to monotonicity vector
        with self.replace_kernel():
            y = super(MonotonicDense, self).call(inputs)

        y = apply_activations(
            y,
            units=self.units,
            activation=self.org_activation,
            is_convex=self.is_convex,
            is_concave=self.is_concave,
            activation_weights=self.activation_weights,
        )

        return y
