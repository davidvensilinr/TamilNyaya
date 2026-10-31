"""
test_api.py — Integration tests for FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "TamilNyaya-Bench"


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "kb_record_count" in data
    assert data["kb_record_count"] >= 25


def test_kb_search_endpoint():
    response = client.get("/api/kb/search?limit=5")
    assert response.status_code == 200
    records = response.json()
    assert len(records) > 0
    first = records[0]
    assert "record_id" in first
    assert "source_file_sha256" in first
    assert "text_ta" in first


def test_kb_coverage_endpoint():
    response = client.get("/api/kb/coverage")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 5


def test_dataset_stats_endpoint():
    response = client.get("/api/dataset/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] >= 100


def test_taxonomy_endpoint():
    response = client.get("/api/taxonomy")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert len(data["categories"]) >= 10


def test_explain_metric_endpoint():
    response = client.get("/api/metrics/citation_accuracy/explain")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Citation Accuracy"
    assert "formula" in data


def test_live_check_layer1():
    payload = {
        "question": "பிரிவு 4 என்ன கூறுகிறது?",
        "answer": "தமிழ்நாடு பெண்கள் வன்கொடுமை தடுப்புச் சட்டம், 1998 பிரிவு 4 இன் கீழ் தண்டனை வழங்கப்படும்.",
        "required_jurisdiction": "Tamil Nadu",
        "run_faithfulness": False,
        "run_judge": False,
    }
    response = client.post("/api/check", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "layer1" in data
    assert data["layer1"]["total_citations"] >= 1
