"""Property-based test: the model must behave on every wind the forecast can send,
including gales above anything in the training data.

Units: the test speaks KNOTS, like the data and the API. The model still receives km/h through knots_to_kmh.
"""
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gozo_ferry.config import data_path, load_config
from gozo_ferry.data import load_data, training_window
from gozo_ferry.features import knots_to_kmh
from gozo_ferry.model import train_model

CONFIG = load_config()
# The strongest wind a forecast could plausibly send, with headroom: a business number, not a sample statistic.
MAX_WIND_KNOTS = 80.0


@pytest.fixture(scope="module")
def model():
    # The same rows the gate trains on, so this tests the model that ships.
    df = knots_to_kmh(training_window(load_data(data_path(CONFIG)), CONFIG), CONFIG["knots_to_kmh"])
    return train_model(df, seed=CONFIG["seed"])


def prob(model, wind_knots):
    df = knots_to_kmh(pd.DataFrame({"wind": [wind_knots]}), CONFIG["knots_to_kmh"])
    return float(model.predict_proba(df[["wind"]])[0][1])


@settings(max_examples=200, deadline=None)
@given(wind=st.floats(min_value=0.0, max_value=MAX_WIND_KNOTS))
def test_probability_is_a_probability(model, wind):
    assert 0.0 <= prob(model, wind) <= 1.0


@settings(max_examples=200, deadline=None)
@given(a=st.floats(min_value=0.0, max_value=MAX_WIND_KNOTS), b=st.floats(min_value=0.0, max_value=MAX_WIND_KNOTS))
def test_stronger_wind_never_makes_cancellation_less_likely(model, a, b):
    calm, strong = sorted((a, b))
    assert prob(model, strong) >= prob(model, calm) - 1e-9
