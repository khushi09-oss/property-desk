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
