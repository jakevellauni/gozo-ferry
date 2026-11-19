"""The API serves only once a model is loaded (Session 6, Stage 15). No registry needed: a local file stands in."""
import importlib
import time

import pytest
from fastapi.testclient import TestClient

from gozo_ferry.features import knots_to_kmh
from gozo_ferry.model import save_model, train_model


@pytest.fixture
def model_file(tmp_path, sample_df):
    path = tmp_path / "model.joblib"
    save_model(train_model(knots_to_kmh(sample_df, 1.852), seed=42), path)
    return str(path)


def test_ready_and_predict_with_a_model(monkeypatch, model_file):
    monkeypatch.setenv("MODEL_URI", model_file)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import gozo_ferry.api as api
    api = importlib.reload(api)
    with TestClient(api.app) as client:
        for _ in range(50):          # the model loads in the background
            if client.get("/ready").status_code == 200:
                break
            time.sleep(0.1)
        assert client.get("/ready").json()["ready"] is True
        body = client.post("/predict", json={"wind": 20}).json()
        assert 0 <= body["probability_cancelled"] <= 1
        assert isinstance(body["warning"], bool)
        assert body["model_version"] == f"file:{model_file}"


def test_alive_but_not_ready_without_a_model(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_URI", str(tmp_path / "missing.joblib"))
    import gozo_ferry.api as api
    api = importlib.reload(api)
    with TestClient(api.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert client.post("/predict", json={"wind": 20}).status_code == 503
