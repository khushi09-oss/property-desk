"""Bounded HTTP collection. Challenged/denied pages never replace the snapshot."""

import json
import re
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.knowledge import HOSTS, ROOT, Knowledge

AGENT = "PropertyResearchAssignment"


class CollectionError(Exception):
    """An explicit source-access or content-quality failure."""


def read_bounded(client: httpx.Client, url: str) -> tuple[str, str]:
    with client.stream("GET", url, headers={"User-Agent": AGENT}) as response:
        if response.status_code != 200:
            raise CollectionError(f"HTTP {response.status_code}")
        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > 2_000_000:
                raise CollectionError("Source exceeds the 2 MB limit")
        text = bytes(content).decode("utf-8", errors="replace")
        if "_incapsula_resource" in text.lower() or "just a moment" in text.lower():
            raise CollectionError("Bot-protection challenge; no content collected")
        return text, response.headers.get("content-type", "")


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.select("script, style, form, nav, header, footer, noscript"):
        node.decompose()
    main = soup.find("main") or soup.find("article") or soup
    blocks = []
    for node in main.find_all(["h1", "h2", "h3", "p", "li"]):
        text = " ".join(node.stripped_strings)
        if not text or re.search(r"@|\+\d[\d\s().-]{7,}\d", text):
            continue
        if re.search(r"\b(?:visa|tax|roi|investment return)\b", text, re.IGNORECASE):
            continue
        if text not in blocks:
            blocks.append(text)
    result = "\n".join(blocks)[:4000]
    if len(result) < 50:
        raise CollectionError("Insufficient readable content")
    return result


def collect_page(client: httpx.Client, url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in HOSTS
        or parsed.username
        or parsed.password
        or parsed.port
    ):
        raise CollectionError("Source is not an approved official HTTPS host")
    robots_url = f"https://{parsed.netloc}/robots.txt"
    try:
        robots_text, kind = read_bounded(client, robots_url)
    except CollectionError as error:
        raise CollectionError(f"Cannot verify robots policy: {error}") from error
    if "text/plain" not in kind:
        raise CollectionError("Cannot verify robots policy: expected plain text")
    policy = RobotFileParser()
    policy.parse(robots_text.splitlines())
    if not policy.can_fetch(AGENT, url):
        raise CollectionError("Access denied by robots policy")
    html, kind = read_bounded(client, url)
    if "html" not in kind:
        raise CollectionError("Expected an HTML page")
    return extract_text(html)


def main() -> None:
    report: dict[str, object] = {
        "collected_at": datetime.now(UTC).isoformat(),
        "pages": [],
    }
    pages = []
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        for url in dict.fromkeys(doc.url for doc in Knowledge.load().documents):
            try:
                pages.append(
                    {
                        "url": url,
                        "text": collect_page(client, url),
                        "status": "collected-for-review",
                    }
                )
            except (CollectionError, httpx.HTTPError) as error:
                pages.append(
                    {
                        "url": url,
                        "status": "failed",
                        "reason": str(error)
                        if isinstance(error, CollectionError)
                        else type(error).__name__,
                    }
                )
            time.sleep(1)
    report["pages"] = pages
    output = ROOT / ".private/collection.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    successful = sum(page["status"] == "collected-for-review" for page in pages)
    print(
        json.dumps(
            {
                "collected": successful,
                "failed": len(pages) - successful,
                "snapshot_replaced": False,
            }
        )
    )


if __name__ == "__main__":
    main()
