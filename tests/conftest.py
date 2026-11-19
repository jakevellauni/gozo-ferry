import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_df():
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "wind": rng.uniform(1, 40, 50),
        "cancelled": rng.integers(0, 2, 50),
    })
