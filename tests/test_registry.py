"""Tests for backend path inference in registry."""

from annotation_extractor.registry import get_backend


def test_get_backend_infers_kindle_from_my_clippings(tmp_path):
    clippings = tmp_path / "My Clippings.txt"
    clippings.write_text("", encoding="utf-8")

    backend = get_backend(db_path=str(clippings))
    assert backend.name == "kindle"


def test_get_backend_infers_boox_from_annotation_txt(tmp_path):
    export = tmp_path / "Book-annotation-2024-01-01_10_00_00.txt"
    export.write_text("", encoding="utf-8")

    backend = get_backend(db_path=str(export))
    assert backend.name == "boox"


def test_get_backend_infers_kindle_from_notebooks_dir(tmp_path):
    notebooks = tmp_path / ".notebooks"
    notebooks.mkdir()

    backend = get_backend(db_path=str(notebooks))
    assert backend.name == "kindle"


def test_get_backend_infers_boox_from_backup_zip(tmp_path):
    backup = tmp_path / "note-backup.zip"
    backup.write_bytes(b"dummy")

    backend = get_backend(db_path=str(backup))
    assert backend.name == "boox"


def test_get_backend_infers_kobo_from_sqlite(tmp_path):
    sqlite_path = tmp_path / "KoboReader.sqlite"
    sqlite_path.write_bytes(b"dummy")

    backend = get_backend(db_path=str(sqlite_path))
    assert backend.name == "kobo"
