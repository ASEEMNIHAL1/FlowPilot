def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "FlowPilot"
    assert body["timezone"] == "Asia/Kolkata"
    assert body["provider_mode"] == "dev"
    assert body["llm_configured"] is False
