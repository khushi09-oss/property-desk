import asyncio
import os
import re
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.cache import PublicAnswerCache
from app.chat import ChatResponse, ModelError, generate_answer
from app.knowledge import ROOT, Knowledge


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1800)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=1200)
    history: list[Turn] = Field(default_factory=list, max_length=4)


class Boundaries:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def secured(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (
                        b"content-security-policy",
                        b"default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
                    ),
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                ]
            await send(message)

        if scope["method"] == "POST" and scope["path"] == "/api/chat":
            body = bytearray()
            try:
                async with asyncio.timeout(10):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > 16_000:
                            await JSONResponse(
                                {"detail": "Request exceeds 16 KB."}, status_code=413
                            )(scope, receive, secured)
                            return
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                await JSONResponse(
                    {"detail": "Request body timed out."}, status_code=408
                )(scope, receive, secured)
                return
            delivered = False

            async def replay() -> Message:
                nonlocal delivered
                if delivered:
                    return await receive()
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}

            await self.app(scope, replay, secured)
        else:
            await self.app(scope, receive, secured)


def create_app() -> FastAPI:
    service = FastAPI(title="Property Desk", docs_url=None, redoc_url=None)
    service.add_middleware(Boundaries)
    knowledge = Knowledge.load()
    answer_cache = PublicAnswerCache()
    slots = asyncio.Semaphore(2)

    @service.get("/api/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "documents": len(knowledge.documents),
            "snapshot_date": str(max(doc.collected_at for doc in knowledge.documents)),
            "mode": "snapshot",
        }

    @service.post("/api/chat", response_model=ChatResponse)
    async def chat(request: Question) -> ChatResponse:
        if re.search(
            r"\b(?:visa|tax|roi|investment advice|guaranteed returns)\b",
            request.question,
            re.IGNORECASE,
        ):
            return ChatResponse(
                answer="I can help compare published property facts, but cannot verify current legal, tax, immigration or investment advice. Please consult a qualified adviser and the official source.",
                sources=[],
                model=None,
            )
        cached = answer_cache.get(request.question, has_history=bool(request.history))
        if cached is not None:
            return cached
        query = request.question
        if not re.search(
            r"\b(?:dg1|tierra|vagues|wasalt|jeddah)\b", query, re.IGNORECASE
        ):
            previous = next(
                (
                    turn.content
                    for turn in reversed(request.history)
                    if turn.role == "user"
                ),
                "",
            )
            query = previous + " " + query
        documents = knowledge.search(query)
        if not documents:
            return ChatResponse(
                answer="I couldn't find that in the collected snapshot. Try asking about DG1, Tierra Viva, Les Vagues, Wasalt services or the captured Jeddah apartments.",
                sources=[],
                model=None,
            )
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise HTTPException(503, "The AI service has not been configured yet.")
        if slots.locked():
            raise HTTPException(
                429,
                "This instance is handling other questions. Please try again shortly.",
                headers={"Retry-After": "10"},
            )
        async with slots:
            try:
                result = await generate_answer(
                    request.question,
                    documents,
                    [
                        {"role": turn.role, "content": turn.content}
                        for turn in request.history
                    ],
                    key,
                )
                answer_cache.put(request.question, result, has_history=bool(request.history))
                return result
            except ModelError as error:
                raise HTTPException(
                    error.status,
                    str(error),
                    headers={"Retry-After": "60"} if error.status == 429 else None,
                ) from error

    @service.get("/")
    async def index() -> FileResponse:
        return FileResponse(ROOT / "web/index.html")

    @service.get("/app.js")
    async def javascript() -> FileResponse:
        return FileResponse(ROOT / "web/app.js", media_type="text/javascript")

    @service.get("/history.mjs")
    async def history_javascript() -> FileResponse:
        return FileResponse(ROOT / "web/history.mjs", media_type="text/javascript")

    @service.get("/style.css")
    async def stylesheet() -> FileResponse:
        return FileResponse(ROOT / "web/style.css", media_type="text/css")

    @service.get("/fonts/{name}")
    async def font_asset(name: str) -> FileResponse:
        public_fonts = {
            "newsreader-latin.woff2": "font/woff2",
            "public-sans-latin.woff2": "font/woff2",
            "newsreader-OFL.txt": "text/plain",
            "public-sans-OFL.txt": "text/plain",
        }
        if name not in public_fonts:
            raise HTTPException(404, "Not found")
        return FileResponse(ROOT / "web/fonts" / name, media_type=public_fonts[name])

    return service


app = create_app()
