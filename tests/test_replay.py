from fastapi.testclient import TestClient

from logic import main


class DummyClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, json=None):
        # Simulate success
        class Resp:
            status_code = 200

            def raise_for_status(self):
                pass

        return Resp()


def test_replay_step_and_status(tmp_path, monkeypatch):
    # Prepare a small CSV dataset to replay
    csv_file = tmp_path / "data.csv"
    csv_file.write_text("timestamp,value\n2020-01-01 00:00:00,1\n2020-01-01 00:01:00,2\n")

    monkeypatch.setenv("CSV_PATH", str(csv_file))
    monkeypatch.setenv("NODE_RED_URL", "http://localhost:1234")

    # Avoid real HTTP calls to Node-RED by patching the HTTP client
    monkeypatch.setattr(main, "_http_client", lambda: DummyClient())

    client = TestClient(main.app)

    # Reset internal index to ensure deterministic behavior
    main._REPLAY_INDEX = 0

    # One step should advance index and return the correct status
    resp = client.post("/replay/step")
    assert resp.status_code == 200
    assert resp.json()["sent"] == 1
    assert resp.json()["index"] == 1

    # Status should report index=1 and total=2
    resp2 = client.get("/replay/status")
    assert resp2.status_code == 200
    assert resp2.json()["index"] == 1
    assert resp2.json()["total"] == 2

    # Reset should bring index back to zero
    resp3 = client.post("/replay/reset")
    assert resp3.status_code == 200
    assert resp3.json()["index"] == 0
