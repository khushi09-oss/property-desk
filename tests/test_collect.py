import json

import httpx
import pytest

from app.collect import CollectionError, collect_page, extract_text


def test_extracts_content_and_removes_scripts_forms_and_contacts():
    html = "<main><h1>Example project</h1><p>A residential tower with a gym and pool.</p><script>secret()</script><form>Enter your name</form><p>Call +971 50 123 4567</p><p>a@example.com</p></main>"
    text = extract_text(html)
    assert "gym" in text
    assert "secret" not in text
    assert "Enter your name" not in text
    assert "@" not in text
    assert "+971" not in text


@pytest.mark.parametrize(
    "body",
    ['<script src="/_Incapsula_Resource"></script>', "<title>Just a moment...</title>"],
)
def test_http_200_challenges_are_not_mistaken_for_data(body):
    def respond(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
                headers={"Content-Type": "text/plain"},
            )
        return httpx.Response(200, text=body)

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(CollectionError, match="challenge"),
    ):
        collect_page(client, "https://darglobal.co.uk/dg1")


def test_robots_denial_stops_before_page_fetch():
    paths = []

    def respond(request):
        paths.append(request.url.path)
        return httpx.Response(
            200,
            text="User-agent: *\nDisallow: /",
            headers={"Content-Type": "text/plain"},
        )

    with (
        httpx.Client(transport=httpx.MockTransport(respond)) as client,
        pytest.raises(CollectionError, match="robots"),
    ):
        collect_page(client, "https://wasalt.sa/en")
    assert paths == ["/robots.txt"]


def test_refresh_reviews_every_snapshot_url_once_without_replacing_data(tmp_path, monkeypatch, capsys):
    from app import collect
    from app.knowledge import Knowledge

    urls = list(dict.fromkeys(doc.url for doc in Knowledge.load().documents))
    reviewed = []
    snapshot = tmp_path / "data" / "knowledge.json"
    snapshot.parent.mkdir()
    snapshot.write_text("preserve existing data", encoding="utf-8")

    def capture(client, url):
        reviewed.append(url)
        return "Synthetic review-only source text; never a replacement dataset."

    monkeypatch.setattr(collect, "ROOT", tmp_path)
    monkeypatch.setattr(collect, "collect_page", capture)
    monkeypatch.setattr(collect.time, "sleep", lambda seconds: None)
    collect.main()
    assert reviewed == urls
    assert snapshot.read_text(encoding="utf-8") == "preserve existing data"
    assert json.loads(capsys.readouterr().out) == {
        "collected": len(urls), "failed": 0, "snapshot_replaced": False
    }
    report = json.loads((tmp_path / ".private" / "collection.json").read_text(encoding="utf-8"))
    assert all(page["status"] == "collected-for-review" for page in report["pages"])
