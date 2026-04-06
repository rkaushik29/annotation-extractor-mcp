"""Tests for the Kobo backend using an in-memory SQLite database."""

import sqlite3
import pytest
from unittest.mock import patch

from annotation_extractor.backends.kobo import KoboBackend
from annotation_extractor.models import Annotation, Book, ReadingProgress


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE content (
    ContentID TEXT PRIMARY KEY,
    ContentType INTEGER,
    Title TEXT,
    Subtitle TEXT,
    Attribution TEXT,
    ISBN TEXT,
    Publisher TEXT,
    Description TEXT,
    Language TEXT,
    Series TEXT,
    SeriesNumber TEXT,
    DateLastRead TEXT,
    ReadStatus INTEGER DEFAULT 0,
    TimeSpentReading INTEGER DEFAULT 0,
    ___PercentRead REAL DEFAULT 0.0,
    Accessibility INTEGER DEFAULT 1
);

CREATE TABLE Bookmark (
    BookmarkID TEXT PRIMARY KEY,
    VolumeID TEXT,
    ContentID TEXT,
    Text TEXT,
    Annotation TEXT,
    Type INTEGER,
    ChapterProgress REAL,
    DateCreated TEXT,
    DateModified TEXT
);
"""

SEED_DATA = """
INSERT INTO content VALUES
    ('book1', 6, 'Neuromancer', NULL, 'William Gibson', '978-0441569595',
     'Ace Books', 'A cyberpunk novel', 'en', 'Sprawl', '1',
     '2024-01-15', 2, 7200, 0.95, 1),
    ('book2', 6, 'Snow Crash', NULL, 'Neal Stephenson', '978-0553380958',
     'Bantam', 'A sci-fi novel', 'en', NULL, NULL,
     '2024-02-20', 1, 3600, 0.45, 1),
    ('book3', 6, 'No Annotations Book', NULL, 'Some Author', NULL,
     NULL, NULL, 'en', NULL, NULL, NULL, 0, 0, 0.0, 1),
    ('chapter1-1', 999, 'Chapter 1: Chiba City Blues', NULL, NULL, NULL,
     NULL, NULL, NULL, NULL, NULL, NULL, 0, 0, 0.0, 1);

INSERT INTO Bookmark VALUES
    ('bm1', 'book1', 'chapter1-1', 'The sky above the port was the color of television, tuned to a dead channel.',
     NULL, 1, 0.05, '2024-01-10T10:00:00', '2024-01-10T10:00:00'),
    ('bm2', 'book1', 'chapter1-1', 'Cyberspace. A consensual hallucination.',
     'Key definition of cyberspace', 1, 0.15, '2024-01-11T14:30:00', '2024-01-11T14:30:00'),
    ('bm3', 'book2', 'book2', 'The Deliverator belongs to an elite order.',
     NULL, 1, 0.01, '2024-02-18T09:00:00', '2024-02-18T09:00:00');
"""


def _create_test_db() -> str:
    """Create an in-memory test database and return a temp file path."""
    import tempfile
    import os

    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.executescript(SEED_DATA)
    conn.close()
    return path


@pytest.fixture
def db_path(tmp_path):
    """Create a test SQLite database and return its path."""
    path = str(tmp_path / "KoboReader.sqlite")
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.executescript(SEED_DATA)
    conn.close()
    return path


@pytest.fixture
def backend():
    return KoboBackend()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListBooks:
    def test_with_annotations_only(self, backend, db_path):
        books = backend.list_books(db_path=db_path, with_annotations_only=True)
        assert len(books) == 2
        titles = {b.title for b in books}
        assert "Neuromancer" in titles
        assert "Snow Crash" in titles
        assert "No Annotations Book" not in titles

    def test_all_books(self, backend, db_path):
        books = backend.list_books(db_path=db_path, with_annotations_only=False)
        assert len(books) == 3
        titles = {b.title for b in books}
        assert "No Annotations Book" in titles

    def test_returns_book_models(self, backend, db_path):
        books = backend.list_books(db_path=db_path)
        for book in books:
            assert isinstance(book, Book)
            assert book.source == "kobo"

    def test_annotation_count(self, backend, db_path):
        books = backend.list_books(db_path=db_path, with_annotations_only=True)
        neuro = next(b for b in books if b.title == "Neuromancer")
        assert neuro.annotation_count == 2

    def test_to_dict(self, backend, db_path):
        books = backend.list_books(db_path=db_path)
        d = books[0].to_dict()
        assert isinstance(d, dict)
        assert "title" in d
        assert "source" in d


class TestGetAnnotations:
    def test_by_title(self, backend, db_path):
        anns = backend.get_annotations(book_title="Neuromancer", db_path=db_path)
        assert len(anns) == 2
        for a in anns:
            assert isinstance(a, Annotation)
            assert a.source == "kobo"
            assert a.book_title == "Neuromancer"

    def test_by_content_id(self, backend, db_path):
        anns = backend.get_annotations(content_id="book1", db_path=db_path)
        assert len(anns) == 2

    def test_partial_title_match(self, backend, db_path):
        anns = backend.get_annotations(book_title="neuro", db_path=db_path)
        assert len(anns) == 2

    def test_highlights_only(self, backend, db_path):
        anns = backend.get_annotations(
            book_title="Neuromancer", db_path=db_path, highlights_only=True
        )
        assert len(anns) == 1
        assert anns[0].note is None or anns[0].note == ""

    def test_notes_only(self, backend, db_path):
        anns = backend.get_annotations(
            book_title="Neuromancer", db_path=db_path, notes_only=True
        )
        assert len(anns) == 1
        assert anns[0].note == "Key definition of cyberspace"

    def test_requires_title_or_id(self, backend, db_path):
        with pytest.raises(ValueError):
            backend.get_annotations(db_path=db_path)

    def test_chapter_populated(self, backend, db_path):
        anns = backend.get_annotations(book_title="Neuromancer", db_path=db_path)
        assert anns[0].chapter == "Chapter 1: Chiba City Blues"


class TestSearchAnnotations:
    def test_search_highlight_text(self, backend, db_path):
        results = backend.search_annotations(query="television", db_path=db_path)
        assert len(results) == 1
        assert "television" in results[0].highlighted_text

    def test_search_note_text(self, backend, db_path):
        results = backend.search_annotations(query="cyberspace", db_path=db_path)
        assert len(results) >= 1

    def test_search_no_results(self, backend, db_path):
        results = backend.search_annotations(query="xyznotfound", db_path=db_path)
        assert len(results) == 0

    def test_search_returns_annotations(self, backend, db_path):
        results = backend.search_annotations(query="Deliverator", db_path=db_path)
        assert len(results) == 1
        assert results[0].book_title == "Snow Crash"
        assert results[0].source == "kobo"


class TestGetReadingProgress:
    def test_returns_active_books(self, backend, db_path):
        progress = backend.get_reading_progress(db_path=db_path)
        # ReadStatus > 0 means reading or finished
        assert len(progress) == 2
        titles = {p.title for p in progress}
        assert "Neuromancer" in titles
        assert "Snow Crash" in titles
        assert "No Annotations Book" not in titles

    def test_returns_progress_models(self, backend, db_path):
        progress = backend.get_reading_progress(db_path=db_path)
        for p in progress:
            assert isinstance(p, ReadingProgress)
            assert p.source == "kobo"

    def test_percent_read(self, backend, db_path):
        progress = backend.get_reading_progress(db_path=db_path)
        neuro = next(p for p in progress if p.title == "Neuromancer")
        assert neuro.percent_read == 95.0


class TestGetBookDetails:
    def test_by_title(self, backend, db_path):
        book = backend.get_book_details(book_title="Neuromancer", db_path=db_path)
        assert book is not None
        assert book.title == "Neuromancer"
        assert book.author == "William Gibson"
        assert book.isbn == "978-0441569595"
        assert book.publisher == "Ace Books"
        assert book.series == "Sprawl"
        assert book.annotation_count == 2
        assert book.percent_complete == 95.0
        assert book.source == "kobo"

    def test_by_content_id(self, backend, db_path):
        book = backend.get_book_details(content_id="book2", db_path=db_path)
        assert book is not None
        assert book.title == "Snow Crash"

    def test_not_found(self, backend, db_path):
        book = backend.get_book_details(book_title="nonexistent", db_path=db_path)
        assert book is None

    def test_requires_title_or_id(self, backend, db_path):
        with pytest.raises(ValueError):
            backend.get_book_details(db_path=db_path)


class TestDetect:
    def test_detect_returns_none_when_no_device(self, backend):
        # On a machine without a Kobo connected, detect should return None
        # (unless you happen to have one plugged in)
        result = backend.detect()
        # We can't assert None definitively since a device might be connected,
        # but we can verify it returns str or None
        assert result is None or isinstance(result, str)

    def test_resolve_path_with_explicit_path(self, backend, db_path):
        path = backend._resolve_path(db_path)
        assert str(path) == db_path

    def test_resolve_path_missing_file(self, backend):
        with pytest.raises(FileNotFoundError):
            backend._resolve_path("/nonexistent/path.sqlite")

    def test_resolve_path_env_var(self, backend, db_path):
        with patch.dict("os.environ", {"KOBO_DB_PATH": db_path}):
            path = backend._resolve_path(None)
            assert str(path) == db_path
