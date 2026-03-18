from fastapi.testclient import TestClient

from logic import main


def test_root_status():
    client = TestClient(main.app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "Online", "structure": "Verified"}


def test_test_data_missing_csv(tmp_path, monkeypatch):
    # Ensure the app is pointed at a path that does not exist.
    missing_csv = tmp_path / "nope.csv"
    monkeypatch.setenv("CSV_PATH", str(missing_csv))

    client = TestClient(main.app)
    response = client.get("/test-data")
    assert response.status_code == 200
    assert response.json() == {"error": "CSV no encontrado"}


def test_metrics_endpoint_reads_csv(tmp_path, monkeypatch):
    # Prepare a small CSV dataset. The first metric column should be "value".
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("timestamp,value\n2020-01-01 00:00:00,1\n2020-01-01 00:01:00,2\n")

    monkeypatch.setenv("CSV_PATH", str(csv_file))

    client = TestClient(main.app)
    response = client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    assert "# TYPE electricity_value gauge" in text
    assert "electricity_value{meter=\"value\"}" in text


def test_nodered_latest_proxy(monkeypatch):
    class DummyResponse:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            return DummyResponse({"foo": "bar"})

    monkeypatch.setattr(main, "_http_client", lambda: DummyClient())

    client = TestClient(main.app)
    response = client.get("/nodered/latest")

    assert response.status_code == 200
    assert response.json() == {"foo": "bar"}
