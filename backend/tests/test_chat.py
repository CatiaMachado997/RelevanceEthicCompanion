from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "service": "Ethic Companion API",
        "version": "1.0.0",
        "status": "operational",
        "mission": "Trust over Engagement",
        "esl_status": "active",
    }
