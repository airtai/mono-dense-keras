# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/MonoDenseLayer.ipynb.

# %% auto 0
__all__ = ['get_saturated_activation', 'get_activation_functions', 'apply_activations', 'get_monotonicity_indicator',
           'apply_monotonicity_indicator_to_kernel', 'replace_kernel_using_monotonicity_indicator', 'MonoDense']

# %% ../../nbs/MonoDenseLayer.ipynb 3
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from typing import *

import tensorflow as tf
import numpy as np

from numpy.typing import ArrayLike, NDArray
from tensorflow.keras.layers import Dense
from tensorflow.types.experimental import TensorLike

# %% ../../nbs/MonoDenseLayer.ipynb 9
def get_saturated_activation(
    convex_activation: Callable[[TensorLike], TensorLike],
    concave_activation: Callable[[TensorLike], TensorLike],
    a: float = 1.0,
    c: float = 1.0,
) -> Callable[[TensorLike], TensorLike]:
    @tf.function
    def saturated_activation(
        x: TensorLike,
        convex_activation: Callable[[TensorLike], TensorLike] = convex_activation,
        concave_activation: Callable[[TensorLike], TensorLike] = concave_activation,
        a: float = a,
        c: float = c,
    ) -> TensorLike:
        cc = convex_activation(tf.ones_like(x) * c)
        ccc = concave_activation(-tf.ones_like(x) * c)
        return a * tf.where(
            x <= 0,
            convex_activation(x + c) - cc,
            concave_activation(x - c) + cc,
        )

    return saturated_activation  # type: ignore


@lru_cache
def get_activation_functions(
    activation: Optional[Union[str, Callable[[TensorLike], TensorLike]]] = None
) -> Tuple[
    Callable[[TensorLike], TensorLike],
    Callable[[TensorLike], TensorLike],
    Callable[[TensorLike], TensorLike],
]:
    convex_activation = tf.keras.activations.get(
        activation.lower() if isinstance(activation, str) else activation
    )

    @tf.function
    def concave_activation(x: TensorLike) -> TensorLike:
        return -convex_activation(-x)

    saturated_activation = get_saturated_activation(
        convex_activation, concave_activation
    )
    return convex_activation, concave_activation, saturated_activation

# %% ../../nbs/MonoDenseLayer.ipynb 13
@tf.function
def apply_activations(
    x: TensorLike,
    *,
    units: int,
    convex_activation: Callable[[TensorLike], TensorLike],
    concave_activation: Callable[[TensorLike], TensorLike],
    saturated_activation: Callable[[TensorLike], TensorLike],
    is_convex: bool = False,
    is_concave: bool = False,
    activation_weights: Tuple[float, float, float] = (7.0, 7.0, 2.0),
) -> TensorLike:
    if convex_activation is None:
        return x

    elif is_convex:
        normalized_activation_weights = np.array([1.0, 0.0, 0.0])
    elif is_concave:
        normalized_activation_weights = np.array([0.0, 1.0, 0.0])
    else:
        if len(activation_weights) != 3:
            raise ValueError(f"activation_weights={activation_weights}")
        if (np.array(activation_weights) < 0).any():
            raise ValueError(f"activation_weights={activation_weights}")
        normalized_activation_weights = np.array(activation_weights) / sum(
            activation_weights
        )

    s_convex = round(normalized_activation_weights[0] * units)
    s_concave = round(normalized_activation_weights[1] * units)
    s_saturated = units - s_convex - s_concave

    x_convex, x_concave, x_saturated = tf.split(
        x, (s_convex, s_concave, s_saturated), axis=-1
    )

    y_convex = convex_activation(x_convex)
    y_concave = concave_activation(x_concave)
    y_saturated = saturated_activation(x_saturated)

    y = tf.concat([y_convex, y_concave, y_saturated], axis=-1)

    return y

# %% ../../nbs/MonoDenseLayer.ipynb 17
def get_monotonicity_indicator(
    monotonicity_indicator: ArrayLike,
    *,
    input_shape: Tuple[int, ...],
    units: int,
) -> TensorLike:
    # convert to tensor if needed and make it broadcastable to the kernel
    monotonicity_indicator = np.array(monotonicity_indicator)
    if len(monotonicity_indicator.shape) < 2:
        monotonicity_indicator = np.reshape(monotonicity_indicator, (-1, 1))
    elif len(monotonicity_indicator.shape) > 2:
        raise ValueError(
            f"monotonicity_indicator has rank greater than 2: {monotonicity_indicator.shape}"
        )

    monotonicity_indicator_broadcasted = np.broadcast_to(
        monotonicity_indicator, shape=(input_shape[-1], units)
    )

    if not np.all(
        (monotonicity_indicator == -1)
        | (monotonicity_indicator == 0)
        | (monotonicity_indicator == 1)
    ):
        raise ValueError(
            f"Each element of monotonicity_indicator must be one of -1, 0, 1, but it is: '{monotonicity_indicator}'"
        )
    return monotonicity_indicator

# %% ../../nbs/MonoDenseLayer.ipynb 21
def apply_monotonicity_indicator_to_kernel(
    kernel: tf.Variable,
    monotonicity_indicator: ArrayLike,
) -> TensorLike:
    # convert to tensor if needed and make it broadcastable to the kernel
    monotonicity_indicator = tf.convert_to_tensor(monotonicity_indicator)

    # absolute value of the kernel
    abs_kernel = tf.abs(kernel)

    # replace original kernel values for positive or negative ones where needed
    xs = tf.where(
        monotonicity_indicator == 1,
        abs_kernel,
        kernel,
    )
    xs = tf.where(monotonicity_indicator == -1, -abs_kernel, xs)

    return xs


@contextmanager
def replace_kernel_using_monotonicity_indicator(
    layer: tf.keras.layers.Dense,
    monotonicity_indicator: TensorLike,
) -> Generator[None, None, None]:
    old_kernel = layer.kernel

    layer.kernel = apply_monotonicity_indicator_to_kernel(
        layer.kernel, monotonicity_indicator
    )
    try:
        yield
    finally:
        layer.kernel = old_kernel


replace_kernel_using_monotonicity_indicator.__module__ = "mono_dense_keras"

# %% ../../nbs/MonoDenseLayer.ipynb 28
class MonoDense(Dense):
    """Monotonic counterpart of the regular Dense Layer of tf.keras"""

    def __init__(
        self,
        units: int,
        *,
        activation: Optional[Union[str, Callable[[TensorLike], TensorLike]]] = None,
        monotonicity_indicator: ArrayLike = 1,
        is_convex: bool = False,
        is_concave: bool = False,
        activation_weights: Tuple[float, float, float] = (7.0, 7.0, 2.0),
        **kwargs: Dict[str, Any],
    ):
        """Constructs a new MonoDense instance.

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
            **kwargs: passed as kwargs to the constructor of `Dense`

        Raise:
            ValueError:
                - if both **is_concave** and **is_convex** are set to **True**, or
                - if any component of activation_weights is negative or there is not exactly three components
        """
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

        super(MonoDense, self).__init__(units=units, activation=None, **kwargs)

        self.units = units
        self.org_activation = activation
        self.activation_weights = activation_weights
        self.monotonicity_indicator = monotonicity_indicator
        self.is_convex = is_convex
        self.is_concave = is_concave

        (
            self.convex_activation,
            self.concave_activation,
            self.saturated_activation,
        ) = get_activation_functions(self.org_activation)

    def build(
        self, input_shape: Tuple, *args: List[Any], **kwargs: Dict[str, Any]
    ) -> None:
        """Build

        Args:
            input_shape: input tensor
            args: positional arguments passed to Dense.build()
            kwargs: keyword arguments passed to Dense.build()
        """
        super(MonoDense, self).build(input_shape, *args, **kwargs)
        self.monotonicity_indicator = get_monotonicity_indicator(
            monotonicity_indicator=self.monotonicity_indicator,
            input_shape=input_shape,
            units=self.units,
        )

    def call(self, inputs: TensorLike) -> TensorLike:
        """Call

        Args:
            inputs: input tensor of shape (batch_size, ..., x_length)

        Returns:
            N-D tensor with shape: `(batch_size, ..., units)`.

        """
        # calculate W'*x+y after we replace the kernal according to monotonicity vector
        with replace_kernel_using_monotonicity_indicator(
            self, monotonicity_indicator=self.monotonicity_indicator
        ):
            h = super(MonoDense, self).call(inputs)

        y = apply_activations(
            h,
            units=self.units,
            convex_activation=self.convex_activation,
            concave_activation=self.concave_activation,
            saturated_activation=self.saturated_activation,
            is_convex=self.is_convex,
            is_concave=self.is_concave,
            activation_weights=self.activation_weights,
        )

        return y


MonoDense.__module__ = "mono_dense_keras"