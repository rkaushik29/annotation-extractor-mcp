"""Tests for the Boox backend."""

import codecs

import pytest

from annotation_extractor.backends.boox import (
    BooxBackend,
    _parse_boox_file,
)
from annotation_extractor.models import Annotation, Book, ReadingProgress


SAMPLE_BOOX_NEUROMANCER = """\
Reading Notes | <<Neuromancer - Gibson, William__abc123-def456>>
Gibson, William. 2024-01-15 10:30 | Page No. : 5
The sky above the port was the color of television, tuned to a dead channel.

Gibson, William. 2024-01-15 10:35 | Page No. : 5
Cyberspace. A consensual hallucination experienced daily by billions.

Key definition of cyberspace

Gibson, William. 2024-01-16 14:00 | Page No. : 69
Night City was like a deranged experiment in social Darwinism.
"""

SAMPLE_BOOX_SNOWCRASH = """\
Reading Notes | <<Snow Crash - Stephenson, Neal__789xyz>>
Stephenson, Neal. 2024-02-21 09:00 | Page No. : 1
The Deliverator belongs to an elite order, a hallowed subcategory.
"""


@pytest.fixture
def export_dir(tmp_path):
    f1 = tmp_path / "Neuromancer-annotation-2024-01-16_14_00_00.txt"
    f1.write_text(SAMPLE_BOOX_NEUROMANCER, encoding="utf-8")
    f2 = tmp_path / "Snow Crash-annotation-2024-02-21_09_00.txt"
    f2.write_text(SAMPLE_BOOX_SNOWCRASH, encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def backend():
    return BooxBackend()


# ------------------------------------------------------------------
# Parser unit tests
# ------------------------------------------------------------------


class TestParseBooxFile:
    def test_parses_header_title_and_author(self, tmp_path):
        f = tmp_path / "test-annotation-2024-01-01_00_00_00.txt"
        f.write_text(SAMPLE_BOOX_NEUROMANCER, encoding="utf-8")
        book = _parse_boox_file(f)
        assert book is not None
        assert book.title == "Neuromancer"
        assert book.author == "Gibson, William"

    def test_parses_uuid(self, tmp_path):
        f = tmp_path / "test-annotation-2024-01-01_00_00_00.txt"
        f.write_text(SAMPLE_BOOX_NEUROMANCER, encoding="utf-8")
        book = _parse_boox_file(f)
        assert book is not None
        assert book.content_id == "abc123-def456"

    def test_parses_annotation_count(self, tmp_path):
        f = tmp_path / "test-annotation-2024-01-01_00_00_00.txt"
        f.write_text(SAMPLE_BOOX_NEUROMANCER, encoding="utf-8")
        book = _parse_boox_file(f)
        assert book is not None
        assert len(book.annotations) == 3

    def test_parses_page_number(self, tmp_path):
        f = tmp_path / "test-annotation-2024-01-01_00_00_00.txt"
        f.write_text(SAMPLE_BOOX_NEUROMANCER, encoding="utf-8")
        book = _parse_boox_file(f)
        assert book.annotations[0].page == 5
        assert book.annotations[2].page == 69

    def test_parses_date(self, tmp_path):
        f = tmp_path / "test-annotation-2024-01-01_00_00_00.txt"
        f.write_text(SAMPLE_BOOX_NEUROMANCER, encoding="utf-8")
        book = _parse_boox_file(f)
        assert book.annotations[0].date_added is not None
        assert book.annotations[0].date_added.year == 2024
        assert book.annotations[0].date_added.month == 1
        assert book.annotations[0].date_added.hour == 10

    def test_parses_highlight_text(self, tmp_path):
        f = tmp_path / "test-annotation-2024-01-01_00_00_00.txt"
        f.write_text(SAMPLE_BOOX_NEUROMANCER, encoding="utf-8")
        book = _parse_boox_file(f)
        assert "television" in book.annotations[0].highlighted_text

    def test_parses_note_text(self, tmp_path):
        f = tmp_path / "test-annotation-2024-01-01_00_00_00.txt"
        f.write_text(SAMPLE_BOOX_NEUROMANCER, encoding="utf-8")
        book = _parse_boox_file(f)
        # Second annotation has a note separated by blank line
        assert book.annotations[1].note == "Key definition of cyberspace"

    def test_highlight_without_note(self, tmp_path):
        f = tmp_path / "test-annotation-2024-01-01_00_00_00.txt"
        f.write_text(SAMPLE_BOOX_NEUROMANCER, encoding="utf-8")
        book = _parse_boox_file(f)
        # First annotation has no note
        assert book.annotations[0].note is None

    def test_multiline_highlight(self, tmp_path):
        text = """\
Reading Notes | <<Test Book - Author__uuid1>>
Author. 2024-01-01 12:00 | Page No. : 1
Line one of the highlight.
Line two of the highlight.
Line three.
"""
        f = tmp_path / "test-annotation-2024-01-01_12_00_00.txt"
        f.write_text(text, encoding="utf-8")
        book = _parse_boox_file(f)
        assert book is not None
        assert len(book.annotations) == 1
        assert "Line one" in book.annotations[0].highlighted_text
        assert "Line two" in book.annotations[0].highlighted_text
        assert "Line three" in book.annotations[0].highlighted_text

    def test_header_without_author(self, tmp_path):
        text = """\
Reading Notes | <<My Personal Document>>
Unknown. 2024-01-01 12:00 | Page No. : 1
Some highlighted text.
"""
        f = tmp_path / "test-annotation-2024-01-01_12_00_00.txt"
        f.write_text(text, encoding="utf-8")
        book = _parse_boox_file(f)
        assert book is not None
        assert book.title == "My Personal Document"
        assert book.author is None

    def test_header_without_uuid(self, tmp_path):
        text = """\
Reading Notes | <<Test Book - Some Author>>
Some Author. 2024-01-01 12:00 | Page No. : 1
Some text.
"""
        f = tmp_path / "test-annotation-2024-01-01_12_00_00.txt"
        f.write_text(text, encoding="utf-8")
        book = _parse_boox_file(f)
        assert book is not None
        assert book.title == "Test Book"
        assert book.author == "Some Author"
        assert book.content_id is None

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty-annotation-2024-01-01_12_00_00.txt"
        f.write_text("", encoding="utf-8")
        book = _parse_boox_file(f)
        assert book is None

    def test_malformed_file_skipped(self, tmp_path):
        f = tmp_path / "bad-annotation-2024-01-01_12_00_00.txt"
        f.write_text("This is not a Boox file at all.\nJust random text.", encoding="utf-8")
        book = _parse_boox_file(f)
        assert book is None

    def test_utf8_bom(self, tmp_path):
        f = tmp_path / "bom-annotation-2024-01-01_12_00_00.txt"
        bom_text = codecs.BOM_UTF8.decode("utf-8") + SAMPLE_BOOX_NEUROMANCER
        f.write_text(bom_text, encoding="utf-8")
        book = _parse_boox_file(f)
        assert book is not None
        assert book.title == "Neuromancer"

    def test_last_date_tracked(self, tmp_path):
        f = tmp_path / "test-annotation-2024-01-01_00_00_00.txt"
        f.write_text(SAMPLE_BOOX_NEUROMANCER, encoding="utf-8")
        book = _parse_boox_file(f)
        assert book.last_date is not None
        assert book.last_date.day == 16  # Jan 16 is the latest


# ------------------------------------------------------------------
# list_books
# ------------------------------------------------------------------


class TestListBooks:
    def test_with_annotations_only(self, backend, export_dir):
        books = backend.list_books(db_path=export_dir, with_annotations_only=True)
        assert len(books) == 2

    def test_all_books(self, backend, export_dir):
        books = backend.list_books(db_path=export_dir, with_annotations_only=False)
        assert len(books) == 2

    def test_returns_book_models(self, backend, export_dir):
        books = backend.list_books(db_path=export_dir)
        for book in books:
            assert isinstance(book, Book)
            assert book.source == "boox"

    def test_annotation_count(self, backend, export_dir):
        books = backend.list_books(db_path=export_dir)
        by_title = {b.title: b for b in books}
        assert by_title["Neuromancer"].annotation_count == 3
        assert by_title["Snow Crash"].annotation_count == 1

    def test_content_id_is_uuid(self, backend, export_dir):
        books = backend.list_books(db_path=export_dir)
        by_title = {b.title: b for b in books}
        assert by_title["Neuromancer"].content_id == "abc123-def456"
        assert by_title["Snow Crash"].content_id == "789xyz"

    def test_to_dict(self, backend, export_dir):
        books = backend.list_books(db_path=export_dir)
        d = books[0].to_dict()
        assert isinstance(d, dict)
        assert "title" in d

    def test_limit(self, backend, export_dir):
        books = backend.list_books(db_path=export_dir, limit=1)
        assert len(books) == 1


# ------------------------------------------------------------------
# get_annotations
# ------------------------------------------------------------------


class TestGetAnnotations:
    def test_by_title(self, backend, export_dir):
        anns = backend.get_annotations(
            book_title="Neuromancer", db_path=export_dir
        )
        assert len(anns) > 0
        for a in anns:
            assert a.book_title == "Neuromancer"

    def test_by_content_id(self, backend, export_dir):
        anns = backend.get_annotations(
            content_id="abc123-def456", db_path=export_dir
        )
        assert len(anns) == 3
        for a in anns:
            assert a.book_title == "Neuromancer"

    def test_partial_title_match(self, backend, export_dir):
        anns = backend.get_annotations(
            book_title="neuro", db_path=export_dir
        )
        assert len(anns) > 0

    def test_highlights_only(self, backend, export_dir):
        anns = backend.get_annotations(
            book_title="Neuromancer",
            db_path=export_dir,
            highlights_only=True,
        )
        for a in anns:
            assert a.highlighted_text is not None
            assert a.note is None

    def test_notes_only(self, backend, export_dir):
        anns = backend.get_annotations(
            book_title="Neuromancer",
            db_path=export_dir,
            notes_only=True,
        )
        assert len(anns) > 0
        for a in anns:
            assert a.note is not None

    def test_requires_book_title_or_content_id(self, backend, export_dir):
        with pytest.raises(ValueError, match="Provide either"):
            backend.get_annotations(db_path=export_dir)

    def test_returns_annotation_models(self, backend, export_dir):
        anns = backend.get_annotations(
            book_title="Snow Crash", db_path=export_dir
        )
        for a in anns:
            assert isinstance(a, Annotation)
            assert a.source == "boox"

    def test_note_paired_with_highlight(self, backend, export_dir):
        anns = backend.get_annotations(
            book_title="Neuromancer", db_path=export_dir
        )
        paired = [a for a in anns if a.highlighted_text and a.note]
        assert len(paired) == 1
        assert "consensual hallucination" in paired[0].highlighted_text
        assert paired[0].note == "Key definition of cyberspace"


# ------------------------------------------------------------------
# search_annotations
# ------------------------------------------------------------------


class TestSearchAnnotations:
    def test_search_highlight_text(self, backend, export_dir):
        results = backend.search_annotations(
            query="television", db_path=export_dir
        )
        assert len(results) >= 1
        assert any("television" in (r.highlighted_text or "") for r in results)

    def test_search_note_text(self, backend, export_dir):
        results = backend.search_annotations(
            query="definition", db_path=export_dir
        )
        assert len(results) >= 1

    def test_search_no_results(self, backend, export_dir):
        results = backend.search_annotations(
            query="xyznonexistent", db_path=export_dir
        )
        assert results == []

    def test_search_case_insensitive(self, backend, export_dir):
        results = backend.search_annotations(
            query="TELEVISION", db_path=export_dir
        )
        assert len(results) >= 1


# ------------------------------------------------------------------
# get_reading_progress
# ------------------------------------------------------------------


class TestGetReadingProgress:
    def test_returns_all_books(self, backend, export_dir):
        progress = backend.get_reading_progress(db_path=export_dir)
        assert len(progress) == 2

    def test_returns_progress_models(self, backend, export_dir):
        progress = backend.get_reading_progress(db_path=export_dir)
        for p in progress:
            assert isinstance(p, ReadingProgress)
            assert p.source == "boox"

    def test_limited_fields_are_none(self, backend, export_dir):
        progress = backend.get_reading_progress(db_path=export_dir)
        for p in progress:
            assert p.percent_read is None
            assert p.time_spent_minutes is None
            assert p.read_status is None

    def test_last_read_populated(self, backend, export_dir):
        progress = backend.get_reading_progress(db_path=export_dir)
        for p in progress:
            assert p.last_read is not None


# ------------------------------------------------------------------
# get_book_details
# ------------------------------------------------------------------


class TestGetBookDetails:
    def test_by_title(self, backend, export_dir):
        book = backend.get_book_details(
            book_title="Neuromancer", db_path=export_dir
        )
        assert book is not None
        assert book.title == "Neuromancer"
        assert book.author == "Gibson, William"

    def test_by_content_id(self, backend, export_dir):
        book = backend.get_book_details(
            content_id="789xyz", db_path=export_dir
        )
        assert book is not None
        assert book.title == "Snow Crash"

    def test_not_found(self, backend, export_dir):
        book = backend.get_book_details(
            book_title="Nonexistent Book", db_path=export_dir
        )
        assert book is None

    def test_requires_title_or_id(self, backend, export_dir):
        with pytest.raises(ValueError, match="Provide either"):
            backend.get_book_details(db_path=export_dir)

    def test_annotation_count(self, backend, export_dir):
        book = backend.get_book_details(
            book_title="Snow Crash", db_path=export_dir
        )
        assert book is not None
        assert book.annotation_count == 1


# ------------------------------------------------------------------
# detect / path resolution
# ------------------------------------------------------------------


class TestDetect:
    def test_detect_returns_none_when_no_device(self, backend):
        result = backend.detect()
        assert result is None or isinstance(result, str)

    def test_resolve_path_with_explicit_path(self, backend, export_dir):
        path = backend._resolve_path(export_dir)
        assert path.is_dir()

    def test_resolve_path_missing_dir(self, backend):
        with pytest.raises(FileNotFoundError):
            backend._resolve_path("/nonexistent/path/boox-export")

    def test_resolve_path_env_var(self, backend, export_dir, monkeypatch):
        monkeypatch.setenv("BOOX_EXPORT_PATH", export_dir)
        path = backend._resolve_path(None)
        assert path.is_dir()

    def test_resolve_path_single_file_uses_parent(self, backend, export_dir, tmp_path):
        # Create a file inside a directory with Boox exports
        f = tmp_path / "test-annotation-2024-01-01_00_00_00.txt"
        f.write_text(SAMPLE_BOOX_SNOWCRASH, encoding="utf-8")
        path = backend._resolve_path(str(f))
        assert path.is_dir()
        assert path == tmp_path
