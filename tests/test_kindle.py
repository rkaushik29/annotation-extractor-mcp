"""Tests for the Kindle backend."""

import codecs

import pytest

from annotation_extractor.backends.kindle import (
    KindleBackend,
    _parse_clippings,
)
from annotation_extractor.models import Annotation, Book, ReadingProgress


SAMPLE_CLIPPINGS = """\
Neuromancer (Gibson, William)
- Your Highlight on page 5 | Location 70-75 | Added on Monday, January 15, 2024 10:30:00 AM

The sky above the port was the color of television, tuned to a dead channel.
==========
Neuromancer (Gibson, William)
- Your Note on page 5 | Location 70 | Added on Monday, January 15, 2024 10:35:00 AM

Famous opening line
==========
Neuromancer (Gibson, William)
- Your Highlight on page 69 | Location 1050-1060 | Added on Tuesday, January 16, 2024 2:00:00 PM

Cyberspace. A consensual hallucination experienced daily by billions.
==========
Snow Crash (Stephenson, Neal)
- Your Highlight on Location 100-110 | Added on Wednesday, February 21, 2024 9:00:00 AM

The Deliverator belongs to an elite order, a hallowed subcategory.
==========
Snow Crash (Stephenson, Neal)
- Your Bookmark on page 50 | Location 500 | Added on Thursday, February 22, 2024 3:00:00 PM


==========
"""


@pytest.fixture
def clippings_path(tmp_path):
    path = tmp_path / "My Clippings.txt"
    path.write_text(SAMPLE_CLIPPINGS, encoding="utf-8-sig")
    return str(path)


@pytest.fixture
def backend():
    return KindleBackend()


# ------------------------------------------------------------------
# Parser unit tests
# ------------------------------------------------------------------


class TestParseClippings:
    def test_splits_entries_correctly(self):
        entries = _parse_clippings(SAMPLE_CLIPPINGS)
        assert len(entries) == 5

    def test_parses_title_and_author(self):
        entries = _parse_clippings(SAMPLE_CLIPPINGS)
        assert entries[0].book_title == "Neuromancer"
        assert entries[0].author == "Gibson, William"

    def test_parses_highlight_metadata(self):
        entries = _parse_clippings(SAMPLE_CLIPPINGS)
        hl = entries[0]
        assert hl.clip_type == "highlight"
        assert hl.page == 5
        assert hl.location_start == 70
        assert hl.location_end == 75
        assert hl.date_added is not None
        assert hl.date_added.year == 2024
        assert hl.date_added.month == 1

    def test_parses_note_metadata(self):
        entries = _parse_clippings(SAMPLE_CLIPPINGS)
        note = entries[1]
        assert note.clip_type == "note"
        assert note.content == "Famous opening line"

    def test_parses_bookmark_metadata(self):
        entries = _parse_clippings(SAMPLE_CLIPPINGS)
        bm = entries[4]
        assert bm.clip_type == "bookmark"
        assert bm.content == ""

    def test_parses_location_without_page(self):
        entries = _parse_clippings(SAMPLE_CLIPPINGS)
        # Snow Crash highlight has no page
        sc_hl = entries[3]
        assert sc_hl.page is None
        assert sc_hl.location_start == 100
        assert sc_hl.location_end == 110

    def test_multiline_highlight(self):
        text = """\
Test Book (Author)
- Your Highlight on page 1 | Location 10-20 | Added on Monday, January 1, 2024 12:00:00 PM

Line one of the highlight.
Line two of the highlight.
Line three.
==========
"""
        entries = _parse_clippings(text)
        assert len(entries) == 1
        assert "Line one" in entries[0].content
        assert "Line two" in entries[0].content
        assert "Line three" in entries[0].content

    def test_missing_author(self):
        text = """\
My Personal Document
- Your Highlight on page 1 | Location 5-10 | Added on Monday, January 1, 2024 12:00:00 PM

Some text
==========
"""
        entries = _parse_clippings(text)
        assert len(entries) == 1
        assert entries[0].book_title == "My Personal Document"
        assert entries[0].author is None

    def test_title_with_parentheses(self):
        text = """\
The Book (Volume 1) (Smith, John)
- Your Highlight on page 1 | Location 5-10 | Added on Monday, January 1, 2024 12:00:00 PM

Some text
==========
"""
        entries = _parse_clippings(text)
        assert entries[0].book_title == "The Book (Volume 1)"
        assert entries[0].author == "Smith, John"

    def test_malformed_entry_skipped(self):
        text = """\
Just one line
==========
Valid Book (Author)
- Your Highlight on page 1 | Location 5-10 | Added on Monday, January 1, 2024 12:00:00 PM

Some text
==========
"""
        entries = _parse_clippings(text)
        assert len(entries) == 1
        assert entries[0].book_title == "Valid Book"

    def test_empty_file(self):
        entries = _parse_clippings("")
        assert entries == []

    def test_utf8_bom(self):
        bom_text = codecs.BOM_UTF8.decode("utf-8") + SAMPLE_CLIPPINGS
        entries = _parse_clippings(bom_text)
        assert len(entries) == 5
        assert entries[0].book_title == "Neuromancer"


# ------------------------------------------------------------------
# list_books
# ------------------------------------------------------------------


class TestListBooks:
    def test_with_annotations_only(self, backend, clippings_path):
        books = backend.list_books(db_path=clippings_path, with_annotations_only=True)
        # Both books have highlights/notes
        assert len(books) == 2

    def test_all_books(self, backend, clippings_path):
        books = backend.list_books(
            db_path=clippings_path, with_annotations_only=False
        )
        assert len(books) == 2

    def test_returns_book_models(self, backend, clippings_path):
        books = backend.list_books(db_path=clippings_path)
        for book in books:
            assert isinstance(book, Book)
            assert book.source == "kindle"

    def test_annotation_count(self, backend, clippings_path):
        books = backend.list_books(db_path=clippings_path)
        by_title = {b.title: b for b in books}
        # Neuromancer: 2 highlights + 1 note = 3
        assert by_title["Neuromancer"].annotation_count == 3
        # Snow Crash: 1 highlight (bookmark not counted) = 1
        assert by_title["Snow Crash"].annotation_count == 1

    def test_to_dict(self, backend, clippings_path):
        books = backend.list_books(db_path=clippings_path)
        d = books[0].to_dict()
        assert isinstance(d, dict)
        assert "title" in d

    def test_limit(self, backend, clippings_path):
        books = backend.list_books(db_path=clippings_path, limit=1)
        assert len(books) == 1


# ------------------------------------------------------------------
# get_annotations
# ------------------------------------------------------------------


class TestGetAnnotations:
    def test_by_title(self, backend, clippings_path):
        anns = backend.get_annotations(
            book_title="Neuromancer", db_path=clippings_path
        )
        assert len(anns) > 0
        for a in anns:
            assert a.book_title == "Neuromancer"

    def test_partial_title_match(self, backend, clippings_path):
        anns = backend.get_annotations(
            book_title="neuro", db_path=clippings_path
        )
        assert len(anns) > 0

    def test_highlights_only(self, backend, clippings_path):
        anns = backend.get_annotations(
            book_title="Neuromancer",
            db_path=clippings_path,
            highlights_only=True,
        )
        for a in anns:
            assert a.highlighted_text is not None
            assert a.note is None

    def test_notes_only(self, backend, clippings_path):
        anns = backend.get_annotations(
            book_title="Neuromancer",
            db_path=clippings_path,
            notes_only=True,
        )
        assert len(anns) > 0
        for a in anns:
            assert a.note is not None

    def test_note_highlight_pairing(self, backend, clippings_path):
        anns = backend.get_annotations(
            book_title="Neuromancer", db_path=clippings_path
        )
        # The highlight at location 70 should be paired with the note at location 70
        paired = [
            a for a in anns if a.highlighted_text and a.note
        ]
        assert len(paired) == 1
        assert "sky above the port" in paired[0].highlighted_text
        assert paired[0].note == "Famous opening line"

    def test_requires_book_title_or_content_id(self, backend, clippings_path):
        with pytest.raises(ValueError, match="Provide either"):
            backend.get_annotations(db_path=clippings_path)

    def test_returns_annotation_models(self, backend, clippings_path):
        anns = backend.get_annotations(
            book_title="Snow Crash", db_path=clippings_path
        )
        for a in anns:
            assert isinstance(a, Annotation)
            assert a.source == "kindle"


# ------------------------------------------------------------------
# search_annotations
# ------------------------------------------------------------------


class TestSearchAnnotations:
    def test_search_highlight_text(self, backend, clippings_path):
        results = backend.search_annotations(
            query="television", db_path=clippings_path
        )
        assert len(results) >= 1
        assert any("television" in (r.highlighted_text or "") for r in results)

    def test_search_note_text(self, backend, clippings_path):
        results = backend.search_annotations(
            query="opening line", db_path=clippings_path
        )
        assert len(results) >= 1

    def test_search_no_results(self, backend, clippings_path):
        results = backend.search_annotations(
            query="xyznonexistent", db_path=clippings_path
        )
        assert results == []

    def test_search_case_insensitive(self, backend, clippings_path):
        results = backend.search_annotations(
            query="TELEVISION", db_path=clippings_path
        )
        assert len(results) >= 1


# ------------------------------------------------------------------
# get_reading_progress
# ------------------------------------------------------------------


class TestGetReadingProgress:
    def test_returns_all_books(self, backend, clippings_path):
        progress = backend.get_reading_progress(db_path=clippings_path)
        assert len(progress) == 2

    def test_returns_progress_models(self, backend, clippings_path):
        progress = backend.get_reading_progress(db_path=clippings_path)
        for p in progress:
            assert isinstance(p, ReadingProgress)
            assert p.source == "kindle"

    def test_limited_fields_are_none(self, backend, clippings_path):
        progress = backend.get_reading_progress(db_path=clippings_path)
        for p in progress:
            assert p.percent_read is None
            assert p.time_spent_minutes is None
            assert p.read_status is None

    def test_last_read_populated(self, backend, clippings_path):
        progress = backend.get_reading_progress(db_path=clippings_path)
        for p in progress:
            assert p.last_read is not None


# ------------------------------------------------------------------
# get_book_details
# ------------------------------------------------------------------


class TestGetBookDetails:
    def test_by_title(self, backend, clippings_path):
        book = backend.get_book_details(
            book_title="Neuromancer", db_path=clippings_path
        )
        assert book is not None
        assert book.title == "Neuromancer"
        assert book.author == "Gibson, William"

    def test_not_found(self, backend, clippings_path):
        book = backend.get_book_details(
            book_title="Nonexistent Book", db_path=clippings_path
        )
        assert book is None

    def test_requires_title_or_id(self, backend, clippings_path):
        with pytest.raises(ValueError, match="Provide either"):
            backend.get_book_details(db_path=clippings_path)

    def test_annotation_count(self, backend, clippings_path):
        book = backend.get_book_details(
            book_title="Snow Crash", db_path=clippings_path
        )
        assert book is not None
        assert book.annotation_count == 1  # 1 highlight (bookmark not counted)


# ------------------------------------------------------------------
# detect / path resolution
# ------------------------------------------------------------------


class TestDetect:
    def test_detect_returns_none_when_no_device(self, backend):
        result = backend.detect()
        # May return None or a path depending on the test environment
        assert result is None or isinstance(result, str)

    def test_resolve_path_with_explicit_path(self, backend, clippings_path):
        path = backend._resolve_path(clippings_path)
        assert path.exists()

    def test_resolve_path_missing_file(self, backend):
        with pytest.raises(FileNotFoundError):
            backend._resolve_path("/nonexistent/path/My Clippings.txt")

    def test_resolve_path_env_var(self, backend, clippings_path, monkeypatch):
        monkeypatch.setenv("KINDLE_CLIPPINGS_PATH", clippings_path)
        path = backend._resolve_path(None)
        assert path.exists()
