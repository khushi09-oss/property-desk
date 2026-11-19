from datetime import date

import pytest

from app.cache import PublicAnswerCache
from app.chat import ChatResponse, Source


def answer():
    return ChatResponse(answer="A public fact [1].", model="example/model:free", sources=[
        Source(id="1", title="DG1", url="https://darglobal.co.uk/dg1", collected_at=date(2026, 11, 19))
    ])


def test_public_aliases_share_answer_and_expire_without_sleeping():
    now = [0.0]
    cache = PublicAnswerCache(clock=lambda: now[0])
    cache.put("What is DarGlobal?", answer(), has_history=False)
    hit = cache.get("  DAR GLOBAL  ", has_history=False)
    assert hit is not None and hit.cached
    hit.sources.clear()
    assert cache.get("DarGlobal", has_history=False).sources
    now[0] = 3600.0
    assert cache.get("DarGlobal", has_history=False) is None


def test_private_wording_and_context_never_enter_or_read_shared_cache():
    cache = PublicAnswerCache()
    cache.put("DarGlobal", answer(), has_history=False)
    assert cache.get("DarGlobal", has_history=True) is None
    private = "DarGlobal, my private reference is synthetic-private-value"
    cache.put(private, answer(), has_history=False)
    assert cache.get(private, has_history=False) is None
    cache.put("What amenities does DG1 offer?", answer(), has_history=True)
    assert cache.get("What amenities does DG1 offer?", has_history=False) is None


@pytest.mark.parametrize("missing", ["model", "sources"])
def test_fallbacks_without_a_model_or_sources_are_not_cached(missing):
    cache = PublicAnswerCache()
    response = answer()
    if missing == "model":
        response.model = None
    else:
        response.sources = []
    cache.put("DarGlobal", response, has_history=False)
    assert cache.get("DarGlobal", has_history=False) is None
