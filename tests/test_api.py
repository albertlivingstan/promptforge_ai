from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "PromptForge AI" in r.text

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "model" in data

def test_providers():
    r = client.get("/api/providers")
    assert r.status_code == 200
    data = r.json()
    assert "routes" in data
    assert "auto" in data["routes"]

def test_analyze():
    r = client.post("/api/analyze", json={"prompt": "Explain quicksort to a student in python"})
    assert r.status_code == 200
    data = r.json()
    assert "clarity" in data
    assert data["task_type"] == "coding"

def test_optimize():
    r = client.post("/api/optimize", json={"prompt": "Explain quicksort", "strategies": ["structured", "role_based"]})
    assert r.status_code == 200
    data = r.json()
    assert len(data["candidates"]) == 2

def test_route_preview():
    r = client.post("/api/route-preview", json={"prompt": "Explain quicksort", "route": "auto"})
    assert r.status_code == 200
    data = r.json()
    assert "attempt_order" in data
    assert "reason" in data

def test_run_mock():
    r = client.post("/api/run", json={"prompt": "Explain quicksort", "strategy": "structured", "route": "mock"})
    assert r.status_code == 200
    data = r.json()
    assert data["strategy"] == "structured"
    assert "metrics" in data
    assert data["generation"]["provider"] == "mock"

def test_compare_mock():
    r = client.post("/api/compare", json={"prompt": "Explain quicksort", "strategies": ["structured", "role_based"], "route": "mock"})
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) == 2
    assert "best_strategy" in data

def test_history_and_stats():
    r = client.get("/api/history")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    s = client.get("/api/stats")
    assert s.status_code == 200
    assert "total" in s.json()
