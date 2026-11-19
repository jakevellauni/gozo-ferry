import pandas as pd
import pytest

from gozo_ferry.features import knots_to_kmh
from gozo_ferry.model import train_model


def test_knots_to_kmh_value():
    df = pd.DataFrame({"wind": [10.0]})
    result = knots_to_kmh(df, 1.852)
    assert result["wind"].iloc[0] == pytest.approx(18.52)


def test_knots_to_kmh_does_not_modify_input(sample_df):
    original = sample_df.copy()
    knots_to_kmh(sample_df, 1.852)
    pd.testing.assert_frame_equal(sample_df, original)


def test_training_smoke_and_determinism(sample_df):
    a = train_model(sample_df, seed=42).predict_proba(sample_df[["wind"]])[:, 1]
    b = train_model(sample_df, seed=42).predict_proba(sample_df[["wind"]])[:, 1]
    assert len(a) == len(sample_df)
    assert ((a >= 0) & (a <= 1)).all()
    assert a == pytest.approx(b)
