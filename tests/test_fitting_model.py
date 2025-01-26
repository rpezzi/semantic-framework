import pytest
import numpy as np
from typing import Dict
from semantiva.workflows.fitting_model import (
    PolynomialFittingModel,
)  # Adjust import based on your module structure


@pytest.fixture
def simple_polynomial_data():
    """
    Fixture providing sample (x, y) data for a simple quadratic function y = 2x² + 3x + 1.
    """
    x_values = [1.0, 2.0, 3.0, 4.0, 5.0]
    y_values = [2 * x**2 + 3 * x + 1 for x in x_values]  # Quadratic function
    return x_values, y_values


@pytest.fixture
def linear_data():
    """
    Fixture providing a simple linear dataset y = 5x + 2.
    """
    x_values = np.linspace(0, 10, 10).tolist()
    y_values = [(5 * x + 2) for x in x_values]
    return x_values, y_values


@pytest.fixture
def noisy_data():
    """
    Fixture providing a noisy dataset based on a quadratic function.
    """
    np.random.seed(42)  # Reproducibility
    x_values = np.linspace(-5, 5, 20).tolist()
    y_values = [
        (2 * x**2 + 3 * x + 1 + np.random.normal(0, 0.01)) for x in x_values
    ]  # Adding noise
    return x_values, y_values


def test_polynomial_fit(simple_polynomial_data):
    """
    Tests if the polynomial fitting correctly estimates the coefficients for a quadratic function.
    """
    x_values, y_values = simple_polynomial_data
    model = PolynomialFittingModel(degree=2)
    params = model.fit(x_values, y_values)

    # Check if keys are correctly named
    assert set(params.keys()) == {"coeff_0", "coeff_1", "coeff_2"}

    # Check if the estimated parameters are close to expected values (2, 3, 1)
    assert pytest.approx(params["coeff_2"], abs=0.1) == 2.0  # Quadratic coefficient
    assert pytest.approx(params["coeff_1"], abs=0.1) == 3.0  # Linear coefficient
    assert pytest.approx(params["coeff_0"], abs=0.1) == 1.0  # Constant term


def test_linear_fit(linear_data):
    """
    Tests fitting a linear dataset y = 5x + 2.
    """
    x_values, y_values = linear_data
    model = PolynomialFittingModel(degree=1)
    params = model.fit(x_values, y_values)
