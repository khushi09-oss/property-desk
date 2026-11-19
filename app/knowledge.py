import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent
HOSTS = {"darglobal.co.uk", "www.darglobal.co.uk", "wasalt.sa"}
STOP_WORDS = {
    "a",
    "an",
    "the",
    "what",
    "which",
    "where",
    "when",
    "how",
    "does",
    "do",
    "is",
    "are",
    "of",
    "in",
    "on",
    "for",
    "to",
    "me",
    "can",
    "you",
    "tell",
    "about",
    "have",
    "has",
    "with",
    "i",
    "my",
    "and",
    "or",
    "please",
    "property",
    "properties",
    "project",
    "projects",
    "snapshot",
}


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,50}$")
    title: str = Field(min_length=3, max_length=180)
    publisher: Literal["DarGlobal", "Wasalt"]
    url: str
    text: str = Field(min_length=20, max_length=4000)
    collected_at: date
    method: Literal["web-extraction", "http"]

    @field_validator("url")
    @classmethod
    def primary_source_only(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.hostname not in HOSTS
            or url.username
            or url.password
            or url.port
        ):
            raise ValueError("Only official HTTPS source links are allowed")
        return value

    @field_validator("text", "title")
    @classmethod
    def exclude_contacts(cls, value: str) -> str:
        if re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|\+\d[\d\s().-]{7,}\d", value):
            raise ValueError("Contact information is excluded from the snapshot")
        return value


class Knowledge:
    def __init__(self, documents: list[Document]):
        if not documents or len({doc.id for doc in documents}) != len(documents):
            raise ValueError("Provide nonempty documents with unique ids")
        self.documents = documents
        self.by_id = {doc.id: doc for doc in documents}
        self.lock = Lock()
        self.db = sqlite3.connect(":memory:", check_same_thread=False)
        # English stemming keeps questions about "pools" relevant to "pool" facts.
        # https://sqlite.org/fts5.html#porter_tokenizer
        self.db.execute(
            "CREATE VIRTUAL TABLE documents USING fts5(id UNINDEXED, title, text, tokenize='porter unicode61 remove_diacritics 2')"
        )
        self.db.executemany(
            "INSERT INTO documents VALUES (?, ?, ?)",
            [(doc.id, f"{doc.publisher} {doc.title}", doc.text) for doc in documents],
        )

    @classmethod
    def load(cls, path: Path = ROOT / "data/knowledge.json") -> "Knowledge":
        records = json.loads(path.read_text(encoding="utf-8"))
        return cls([Document.model_validate(record) for record in records])

    def search(self, question: str, limit: int = 4) -> list[Document]:
        question = re.sub(r"\bdar\s+global\b", "DarGlobal", question, flags=re.IGNORECASE)
        terms = list(
            dict.fromkeys(
                term.lower()
                for term in re.findall(r"\w+", question)
                if term.lower() not in STOP_WORDS
            )
        )[:20]
        if not terms:
            return []
        expression = " OR ".join('"' + term + '"' for term in terms)
        with self.lock:
            rows = self.db.execute(
                "SELECT id FROM documents WHERE documents MATCH ? ORDER BY bm25(documents, 0, 5, 1) LIMIT ?",
                (expression, limit),
            ).fetchall()
        found = [self.by_id[row[0]] for row in rows]
        company = self.by_id.get("darglobal-company")
        if "darglobal" in terms and company:
            found = [company, *[doc for doc in found if doc.id != company.id]]
        return found[:limit]
