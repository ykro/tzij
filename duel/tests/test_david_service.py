"""David's GPU service: readiness and translation (retrieval + model), with mock models."""

import httpx

from tzij_duel.david_app import create_app


async def test_health_and_translate(settings, david):
    app = create_app(settings, david)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        health = (await client.get("/health")).json()
        res = await client.post("/translate", json={"text": "El perro duerme en la casa.", "direction": "es-quc"})
        empty = await client.post("/translate", json={"text": "  ", "direction": "es-quc"})
    assert health == {"ready": True, "model": "gemma-test", "retrieval": True}
    body = res.json()
    assert res.status_code == 200 and body["status"] == "ok" and body["text"] and body["model"] == "gemma-test"
    assert empty.status_code == 422


async def test_without_an_index_david_reports_the_error(settings, david):
    david.retriever = None
    app = create_app(settings, david)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        body = (await client.post("/translate", json={"text": "El perro duerme.", "direction": "es-quc"})).json()
    assert body["status"] == "error" and "índice" in body["error"]
