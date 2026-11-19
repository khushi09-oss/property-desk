"""Bounded, instance-local caching of fixed public questions; never chat history."""

from collections.abc import Callable
from time import monotonic

from app.chat import ChatResponse

PUBLIC_QUESTIONS = (
    ("DarGlobal", "Dar Global", "What is DarGlobal?", "What is Dar Global?", "What is DarGlobal and which projects are covered here?"),
    ("What amenities does DG1 offer?",),
    ("Tell me about Tierra Viva villas in Spain.",),
    ("How do I list a property on Wasalt?",),
    ("Compare DG1 and Les Vagues amenities.",),
    ("Which captured Jeddah apartment has the lower asking price?",),
)


def normalize(question: str) -> str:
    return " ".join(question.casefold().split()).rstrip("?.!")


PUBLIC_KEYS = {
    normalize(alias): index
    for index, aliases in enumerate(PUBLIC_QUESTIONS)
    for alias in aliases
}


class PublicAnswerCache:
    def __init__(self, clock: Callable[[], float] = monotonic):
        self.clock = clock
        self.entries: dict[int, tuple[float, ChatResponse]] = {}

    def get(self, question: str, *, has_history: bool) -> ChatResponse | None:
        key = None if has_history else PUBLIC_KEYS.get(normalize(question))
        if key is None or key not in self.entries:
            return None
        expires, response = self.entries[key]
        if self.clock() >= expires:
            del self.entries[key]
            return None
        return response.model_copy(deep=True)

    def put(self, question: str, response: ChatResponse, *, has_history: bool) -> None:
        key = None if has_history else PUBLIC_KEYS.get(normalize(question))
        if key is None or not response.model or not response.sources:
            return
        self.entries[key] = (
            self.clock() + 3600,
            response.model_copy(deep=True, update={"cached": True}),
        )
