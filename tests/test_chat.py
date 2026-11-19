import asyncio
import json

import httpx
import pytest

from app.chat import ModelError, generate_answer
from app.knowledge import Knowledge


def call_with(response, *, question="What amenities does DG1 have?"):
    def respond(request):
        payload = json.loads(request.content)
        assert payload["model"] == "openrouter/free"
        assert "synthetic-key" not in request.content.decode()
        assert "max_tokens" in payload
        context = json.loads(payload["messages"][1]["content"])
        assert all(item["publisher"] in {"DarGlobal", "Wasalt"} for item in context["evidence"])
        return response

    return asyncio.run(
        generate_answer(
            question,
            Knowledge.load().search(question),
            [],
            "synthetic-key",
            httpx.MockTransport(respond),
        )
    )


def test_answer_links_come_from_evidence_not_the_model():
    result = call_with(
        httpx.Response(
            200,
            json={
                "model": "example/model:free",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": "DG1 lists a gym and infinity pool. [1]"
                        },
                    }
                ],
            },
        )
    )
    assert result.sources[0].url == "https://darglobal.co.uk/dg1"
    assert result.sources[0].id == "1"


@pytest.mark.parametrize(
    "content",
    [
        None,
        "",
        "A made-up answer [99]",
        "A real source [1] plus a made-up source [9999]",
        "A factual claim without any citation",
    ],
)
def test_empty_or_uncited_or_fabricated_citations_are_rejected(content):
    with pytest.raises(ModelError) as error:
        call_with(
            httpx.Response(
                200,
                json={
                    "model": "example/model:free",
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": content}}
                    ],
                },
            )
        )
    assert error.value.status == 502


def test_provider_limit_is_a_generic_retryable_error():
    with pytest.raises(ModelError) as error:
        call_with(
            httpx.Response(429, json={"error": {"message": "PRIVATE PROVIDER MESSAGE"}})
        )
    assert error.value.status == 429
    assert "PRIVATE" not in str(error.value)


def test_truncated_answer_is_not_presented_as_complete():
    with pytest.raises(ModelError):
        call_with(
            httpx.Response(
                200,
                json={
                    "model": "example/model:free",
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {"content": "Partial [1]"},
                        }
                    ],
                },
            )
        )


@pytest.mark.parametrize(
    ("finish_reason", "content", "category"),
    [
        ("length", "PRIVATE MODEL OUTPUT [1]", "output_limit"),
        ("stop", None, "empty_answer"),
        ("error", "PRIVATE MODEL OUTPUT [1]", "incomplete_answer"),
    ],
)
def test_incomplete_answer_logs_only_a_safe_category(caplog, finish_reason, content, category):
    with pytest.raises(ModelError):
        call_with(httpx.Response(200, json={
            "model": "example/model:free",
            "choices": [{"finish_reason": finish_reason, "message": {"content": content}}],
        }))
    assert f"reason={category}" in caplog.text
    assert "PRIVATE MODEL OUTPUT" not in caplog.text
    assert "synthetic-key" not in caplog.text


def test_timeout_is_explicit():
    def timeout(request):
        raise httpx.ReadTimeout("sensitive detail")

    with pytest.raises(ModelError) as error:
        asyncio.run(
            generate_answer(
                "DG1",
                Knowledge.load().search("DG1"),
                [],
                "synthetic-key",
                httpx.MockTransport(timeout),
            )
        )
    assert error.value.status == 504


@pytest.mark.parametrize("field", ["answer", "model"])
def test_provider_cannot_reflect_the_configured_key_to_the_browser(field):
    payload = {
        "model": "example/model:free",
        "choices": [{"finish_reason": "stop", "message": {"content": "A pool. [1]"}}],
    }
    if field == "answer":
        payload["choices"][0]["message"]["content"] = "synthetic-key [1]"
    else:
        payload["model"] = "synthetic-key"
    with pytest.raises(ModelError) as error:
        call_with(httpx.Response(200, json=payload))
    assert error.value.status == 502
    assert "synthetic-key" not in str(error.value)
