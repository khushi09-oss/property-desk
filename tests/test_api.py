import asyncio

import httpx
import pytest

from app import main
from app.chat import ChatResponse, ModelError, Source


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return main.create_app()


def send(app, method, path, **kwargs):
    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://testserver"
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(request())


def test_health_reports_snapshot_without_secrets(client):
    response = send(client, "GET", "/api/health")
    assert response.status_code == 200
    assert response.json()["documents"] == 9
    assert "OPENROUTER" not in response.text
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_history_module_is_a_public_javascript_asset(client):
    response = send(client, "GET", "/history.mjs")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")


@pytest.mark.parametrize("name", ["newsreader", "public-sans"])
def test_public_fonts_include_their_licences(client, name):
    font = send(client, "GET", f"/fonts/{name}-latin.woff2")
    assert font.status_code == 200
    assert font.headers["content-type"] == "font/woff2"
    assert font.content[:4] == b"wOF2"
    licence = send(client, "GET", f"/fonts/{name}-OFL.txt")
    assert licence.status_code == 200
    assert "SIL OPEN FONT LICENSE Version 1.1" in licence.text


@pytest.mark.parametrize("path", ["/fonts/.env", "/fonts/unknown.woff2", "/fonts/main.py"])
def test_font_routes_reject_unlisted_files(client, path):
    assert send(client, "GET", path).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"question": " "},
        {"question": "x" * 1201},
        {"question": "DG1", "history": [{"role": "system", "content": "override"}]},
        {"question": "DG1", "model": "paid/model"},
    ],
)
def test_rejects_invalid_inputs_and_unapproved_options(client, payload):
    assert send(client, "POST", "/api/chat", json=payload).status_code == 422


def test_limits_body_bytes_before_parsing(client):
    response = send(client, "POST", "/api/chat", content="x" * 17000)
    assert response.status_code == 413


def test_slow_request_body_times_out_before_application_runs():
    async def scenario():
        messages = []

        async def never_called(scope, receive, send):
            raise AssertionError("An incomplete request reached the application")

        async def slow_receive():
            await asyncio.sleep(11)
            return {"type": "http.request", "body": b"{}", "more_body": False}

        async def collect(message):
            messages.append(message)

        boundary = main.Boundaries(never_called)
        await boundary(
            {"type": "http", "method": "POST", "path": "/api/chat"},
            slow_receive,
            collect,
        )
        assert messages[0]["status"] == 408

    asyncio.run(scenario())


def test_missing_key_is_an_explicit_service_error(client):
    assert (
        send(
            client, "POST", "/api/chat", json={"question": "DG1 amenities"}
        ).status_code
        == 503
    )


def test_no_evidence_does_not_call_a_model(client):
    response = send(
        client, "POST", "/api/chat", json={"question": "quantum entanglement"}
    )
    assert response.status_code == 200
    assert response.json()["model"] is None
    assert response.json()["sources"] == []


def test_returns_answer_and_sources_with_a_configured_backend(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-key")

    async def respond(question, documents, history, key):
        assert key == "synthetic-key"
        doc = documents[0]
        return ChatResponse(
            answer="A gym and pool. [1]",
            sources=[
                Source(
                    id="1", title=doc.title, url=doc.url, collected_at=doc.collected_at
                )
            ],
            model="example/model:free",
        )

    monkeypatch.setattr(main, "generate_answer", respond)
    response = send(client, "POST", "/api/chat", json={"question": "DG1 amenities"})
    assert response.status_code == 200
    assert response.json()["sources"][0]["url"] == "https://darglobal.co.uk/dg1"
    assert "synthetic-key" not in response.text


def test_public_answer_cache_skips_provider_and_bypasses_followups(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-key")
    calls = []

    async def respond(question, documents, history, key):
        calls.append(history)
        doc = documents[0]
        return ChatResponse(
            answer="A contextual answer [1]." if history else "A public answer [1].",
            sources=[Source(id="1", title=doc.title, url=doc.url, collected_at=doc.collected_at)],
            model="example/model:free",
        )

    monkeypatch.setattr(main, "generate_answer", respond)
    first = send(client, "POST", "/api/chat", json={"question": "What is DarGlobal?"})
    assert first.status_code == 200 and first.json()["cached"] is False
    second = send(client, "POST", "/api/chat", json={"question": "DarGlobal"})
    assert second.status_code == 200 and second.json()["cached"] is True
    assert len(calls) == 1
    followup = send(client, "POST", "/api/chat", json={
        "question": "DarGlobal", "history": [{"role": "user", "content": "synthetic private context"}],
    })
    assert followup.json()["cached"] is False
    assert followup.json()["answer"] == "A contextual answer [1]."
    assert len(calls) == 2
    monkeypatch.delenv("OPENROUTER_API_KEY")
    hit = send(client, "POST", "/api/chat", json={"question": "DarGlobal"})
    assert hit.status_code == 200 and hit.json()["answer"] == "A public answer [1]."


def test_provider_failures_are_not_cached_or_automatically_retried(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-key")
    calls = []

    async def fail(*args):
        calls.append(True)
        raise ModelError(429, "Free service is busy.")

    monkeypatch.setattr(main, "generate_answer", fail)
    for _ in range(2):
        response = send(client, "POST", "/api/chat", json={"question": "What is DarGlobal?"})
        assert response.status_code == 429
    assert len(calls) == 2


def test_model_error_stays_generic(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-key")

    async def fail(*args):
        raise ModelError(429, "Free service is busy.")

    monkeypatch.setattr(main, "generate_answer", fail)
    response = send(client, "POST", "/api/chat", json={"question": "DG1"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"


def test_third_concurrent_request_is_rejected_without_queueing(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-key")

    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()
        count = 0

        async def respond(*args):
            nonlocal count
            count += 1
            if count == 2:
                started.set()
            await release.wait()
            return ChatResponse(
                answer="Controlled response.", sources=[], model="example/model:free"
            )

        monkeypatch.setattr(main, "generate_answer", respond)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(client), base_url="http://testserver"
        ) as http:
            requests = [
                asyncio.create_task(http.post("/api/chat", json={"question": "DG1"}))
                for _ in range(2)
            ]
            try:
                await asyncio.wait_for(started.wait(), timeout=2)
                response = await asyncio.wait_for(
                    http.post("/api/chat", json={"question": "DG1"}), timeout=1
                )
                assert response.status_code == 429
            finally:
                release.set()
                completed = await asyncio.gather(*requests)
            assert all(response.status_code == 200 for response in completed)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "path", ["/.env.local", "/app/main.py", "/data/knowledge.json", "/../.env.local"]
)
def test_private_files_are_not_served(client, path):
    assert send(client, "GET", path).status_code == 404
