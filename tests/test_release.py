from pathlib import Path

import pytest

from scripts.prepare_release import FILES, prepare_release


def project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    for source in FILES.values():
        path = root / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("public fixture", encoding="utf-8")
    (root / ".env").write_text("KEY=synthetic-private-value", encoding="utf-8")
    (root / ".private").mkdir()
    (root / ".private/notes.txt").write_text("private fixture", encoding="utf-8")
    return root


def test_release_excludes_environment_and_private_material(tmp_path):
    root = project(tmp_path)
    output = root / ".private/release"
    prepare_release(root, output)
    assert (output / "Dockerfile").is_file()
    assert (output / "app/main.py").is_file()
    assert (output / "data/knowledge.json").is_file()
    assert not (output / ".env").exists()
    assert not (output / ".private").exists()
    assert not (output / ".vercel").exists()
    assert all("synthetic-private-value" not in path.read_text() for path in output.rglob("*") if path.is_file())


def test_existing_output_is_preserved(tmp_path):
    root = project(tmp_path)
    output = tmp_path / "release"
    output.mkdir()
    sentinel = output / "personal.txt"
    sentinel.write_text("keep me", encoding="utf-8")
    with pytest.raises(FileExistsError):
        prepare_release(root, output)
    assert sentinel.read_text() == "keep me"
    assert list(output.iterdir()) == [sentinel]


def test_release_cannot_write_into_application_sources(tmp_path):
    root = project(tmp_path)
    with pytest.raises(ValueError):
        prepare_release(root, root / "web/generated")
    assert not (root / "web/generated").exists()
