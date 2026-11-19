import os

from app import run


def test_local_entrypoint_reads_only_the_model_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("SYNTHETIC_OTHER_SECRET", raising=False)
    monkeypatch.setattr(run, "ROOT", tmp_path)
    (tmp_path / ".env.local").write_text(
        'OPENROUTER_API_KEY="synthetic-key"\nSYNTHETIC_OTHER_SECRET=not-for-the-app\n'
    )
    calls = []
    monkeypatch.setattr(
        run.uvicorn, "run", lambda *args, **kwargs: calls.append(kwargs)
    )
    run.main()
    assert os.environ["OPENROUTER_API_KEY"] == "synthetic-key"
    assert "SYNTHETIC_OTHER_SECRET" not in os.environ
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["access_log"] is False
    monkeypatch.delenv("OPENROUTER_API_KEY")
