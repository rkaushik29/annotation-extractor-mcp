"""Kindle eReader backend.

Reads highlights, annotations, and bookmarks from a Kindle's
My Clippings.txt file.
"""

import logging
import os
import platform
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from annotation_extractor.backends.base import EReaderBackend
from annotation_extractor.models import Annotation, Book, ReadingProgress

logger = logging.getLogger(__name__)

_SEPARATOR = "=========="

# Regex: greedy match captures everything up to the *last* parenthesized group
_TITLE_AUTHOR_RE = re.compile(r"^(.+)\s+\(([^)]+)\)\s*$")

# Metadata line variants:
#   - Your Highlight on page 5 | Location 70-75 | Added on Monday, ...
#   - Your Highlight on Location 70-75 | Added on Monday, ...
_META_RE = re.compile(
    r"^- Your (Highlight|Note|Bookmark)"
    r"(?: on page (\d+) \| [Ll]ocation| on [Ll]ocation)"
    r" (\d+)(?:-(\d+))?"
    r" \| Added on (.+)$"
)

# Fallback: page-only (no location)
_META_PAGE_ONLY_RE = re.compile(
    r"^- Your (Highlight|Note|Bookmark)"
    r" on page (\d+)"
    r" \| Added on (.+)$"
)

_DATE_FORMAT = "%A, %B %d, %Y %I:%M:%S %p"


@dataclass
class _ClippingEntry:
    book_title: str
    author: str | None
    clip_type: str  # "highlight", "note", "bookmark"
    page: int | None
    location_start: int | None
    location_end: int | None
    date_added: datetime | None
    date_added_raw: str | None
    content: str


@dataclass
class _BookData:
    title: str
    author: str | None
    entries: list[_ClippingEntry] = field(default_factory=list)
    last_date: datetime | None = None


def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    try:
        return datetime.strptime(raw, _DATE_FORMAT)
    except ValueError:
        return None


def _parse_clippings(text: str) -> list[_ClippingEntry]:
    """Parse the raw My Clippings.txt content into structured entries."""
    entries: list[_ClippingEntry] = []
    chunks = text.split(_SEPARATOR)

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        lines = chunk.split("\n")
        if len(lines) < 2:
            logger.warning("Skipping malformed clipping entry (too few lines)")
            continue

        # --- Line 1: title and author ---
        title_line = lines[0].strip()
        # Strip BOM if present on first entry
        title_line = title_line.lstrip("\ufeff")
        m_title = _TITLE_AUTHOR_RE.match(title_line)
        if m_title:
            title = m_title.group(1).strip()
            author = m_title.group(2).strip()
        else:
            title = title_line
            author = None

        # --- Line 2: metadata ---
        meta_line = lines[1].strip()
        m_meta = _META_RE.match(meta_line)
        if m_meta:
            clip_type = m_meta.group(1).lower()
            page = int(m_meta.group(2)) if m_meta.group(2) else None
            location_start = int(m_meta.group(3))
            location_end = int(m_meta.group(4)) if m_meta.group(4) else location_start
            date_raw = m_meta.group(5)
            date_added = _parse_date(date_raw)
        else:
            m_page = _META_PAGE_ONLY_RE.match(meta_line)
            if m_page:
                clip_type = m_page.group(1).lower()
                page = int(m_page.group(2))
                location_start = None
                location_end = None
                date_raw = m_page.group(3)
                date_added = _parse_date(date_raw)
            else:
                logger.warning("Skipping entry with unparseable metadata: %s", meta_line)
                continue

        # --- Lines 3+: content ---
        content_lines = lines[2:]
        content = "\n".join(content_lines).strip()

        entries.append(
            _ClippingEntry(
                book_title=title,
                author=author,
                clip_type=clip_type,
                page=page,
                location_start=location_start,
                location_end=location_end,
                date_added=date_added,
                date_added_raw=date_raw,
                content=content,
            )
        )

    return entries


def _group_by_book(entries: list[_ClippingEntry]) -> dict[str, _BookData]:
    """Group clipping entries by book (title + author)."""
    books: dict[str, _BookData] = {}
    for entry in entries:
        key = (entry.book_title.strip().lower(), (entry.author or "").strip().lower())
        key_str = f"{key[0]}||{key[1]}"
        if key_str not in books:
            books[key_str] = _BookData(
                title=entry.book_title.strip(),
                author=entry.author,
            )
        book = books[key_str]
        book.entries.append(entry)
        if entry.date_added:
            if book.last_date is None or entry.date_added > book.last_date:
                book.last_date = entry.date_added
    return books


def _build_annotations(
    entries: list[_ClippingEntry], source: str
) -> list[Annotation]:
    """Build Annotation objects, pairing highlights with notes at the same location."""
    highlights: dict[int | None, _ClippingEntry] = {}
    notes: dict[int | None, _ClippingEntry] = {}
    bookmarks: list[_ClippingEntry] = []

    for entry in entries:
        if entry.clip_type == "highlight":
            highlights[entry.location_start] = entry
        elif entry.clip_type == "note":
            notes[entry.location_start] = entry
        elif entry.clip_type == "bookmark":
            bookmarks.append(entry)

    annotations: list[Annotation] = []
    paired_note_locs: set[int | None] = set()

    # Pair highlights with notes at the same location
    for loc, hl in highlights.items():
        note_entry = notes.get(loc)
        note_text = None
        if note_entry:
            note_text = note_entry.content or None
            paired_note_locs.add(loc)

        annotations.append(
            Annotation(
                book_title=hl.book_title,
                author=hl.author,
                highlighted_text=hl.content or None,
                source=source,
                note=note_text,
                date_created=(
                    hl.date_added.isoformat() if hl.date_added else hl.date_added_raw
                ),
                bookmark_type="highlight",
            )
        )

    # Orphaned notes (no matching highlight)
    for loc, note_entry in notes.items():
        if loc in paired_note_locs:
            continue
        annotations.append(
            Annotation(
                book_title=note_entry.book_title,
                author=note_entry.author,
                highlighted_text=None,
                source=source,
                note=note_entry.content or None,
                date_created=(
                    note_entry.date_added.isoformat()
                    if note_entry.date_added
                    else note_entry.date_added_raw
                ),
                bookmark_type="note",
            )
        )

    # Bookmarks
    for bm in bookmarks:
        annotations.append(
            Annotation(
                book_title=bm.book_title,
                author=bm.author,
                highlighted_text=None,
                source=source,
                note=None,
                date_created=(
                    bm.date_added.isoformat() if bm.date_added else bm.date_added_raw
                ),
                bookmark_type="bookmark",
            )
        )

    # Sort by date
    annotations.sort(key=lambda a: a.date_created or "")
    return annotations


class KindleBackend(EReaderBackend):
    name = "kindle"

    # ------------------------------------------------------------------
    # Detection & path resolution
    # ------------------------------------------------------------------

    def detect(self) -> str | None:
        candidates: list[Path] = []
        system = platform.system()

        if system == "Darwin":
            volumes = Path("/Volumes")
            if volumes.exists():
                for vol in volumes.iterdir():
                    candidate = vol / "documents" / "My Clippings.txt"
                    if candidate.exists():
                        candidates.append(candidate)
        elif system == "Linux":
            for base in [Path("/media"), Path("/mnt"), Path("/run/media")]:
                if not base.exists():
                    continue
                for user_dir in base.iterdir():
                    for device_dir in user_dir.iterdir():
                        candidate = device_dir / "documents" / "My Clippings.txt"
                        if candidate.exists():
                            candidates.append(candidate)
        elif system == "Windows":
            import string

            for letter in string.ascii_uppercase:
                candidate = Path(f"{letter}:") / "documents" / "My Clippings.txt"
                if candidate.exists():
                    candidates.append(candidate)

        return str(candidates[0]) if candidates else None

    def _resolve_path(self, db_path: str | None) -> Path:
        if db_path:
            p = Path(db_path).resolve()
            if p.exists():
                return p
            raise FileNotFoundError(f"Clippings file not found at {p}")

        env = os.environ.get("KINDLE_CLIPPINGS_PATH")
        if env:
            p = Path(env).resolve()
            if p.exists():
                return p
            raise FileNotFoundError(
                f"KINDLE_CLIPPINGS_PATH set but not found: {p}"
            )

        detected = self.detect()
        if detected:
            return Path(detected)

        raise FileNotFoundError(
            "Could not find My Clippings.txt. "
            "Connect your Kindle via USB or set KINDLE_CLIPPINGS_PATH."
        )

    def _load_clippings(
        self, db_path: str | None
    ) -> tuple[dict[str, _BookData], list[_ClippingEntry]]:
        path = self._resolve_path(db_path)
        text = path.read_text(encoding="utf-8-sig")
        entries = _parse_clippings(text)
        books = _group_by_book(entries)
        return books, entries

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def list_books(
        self,
        db_path: str | None = None,
        with_annotations_only: bool = True,
        limit: int | None = None,
    ) -> list[Book]:
        books, _ = self._load_clippings(db_path)
        result: list[Book] = []

        for book_data in books.values():
            annotation_count = sum(
                1 for e in book_data.entries if e.clip_type in ("highlight", "note")
            )
            if with_annotations_only and annotation_count == 0:
                continue

            result.append(
                Book(
                    title=book_data.title,
                    author=book_data.author,
                    source=self.name,
                    annotation_count=annotation_count,
                    last_read=(
                        book_data.last_date.isoformat()
                        if book_data.last_date
                        else None
                    ),
                )
            )

        result.sort(key=lambda b: b.last_read or "", reverse=True)
        effective_limit = limit if limit is not None else self.DEFAULT_LIMIT
        return result[:effective_limit]

    def get_annotations(
        self,
        book_title: str | None = None,
        content_id: str | None = None,
        db_path: str | None = None,
        highlights_only: bool = False,
        notes_only: bool = False,
        limit: int | None = None,
    ) -> list[Annotation]:
        if not book_title and not content_id:
            raise ValueError("Provide either book_title or content_id.")

        books, _ = self._load_clippings(db_path)
        search = (book_title or content_id or "").lower()

        # Collect entries from matching books
        matched_entries: list[_ClippingEntry] = []
        for book_data in books.values():
            if search in book_data.title.lower():
                matched_entries.extend(book_data.entries)

        annotations = _build_annotations(matched_entries, self.name)

        if highlights_only:
            annotations = [
                a
                for a in annotations
                if a.highlighted_text and not a.note
            ]
        elif notes_only:
            annotations = [a for a in annotations if a.note]

        effective_limit = limit if limit is not None else self.DEFAULT_LIMIT
        return annotations[:effective_limit]

    def search_annotations(
        self,
        query: str,
        db_path: str | None = None,
        limit: int | None = None,
    ) -> list[Annotation]:
        books, _ = self._load_clippings(db_path)
        all_entries: list[_ClippingEntry] = []
        for book_data in books.values():
            all_entries.extend(book_data.entries)

        annotations = _build_annotations(all_entries, self.name)
        q = query.lower()
        matched = [
            a
            for a in annotations
            if (a.highlighted_text and q in a.highlighted_text.lower())
            or (a.note and q in a.note.lower())
        ]

        effective_limit = limit if limit is not None else self.DEFAULT_LIMIT
        return matched[:effective_limit]

    def get_reading_progress(
        self,
        db_path: str | None = None,
        limit: int | None = None,
    ) -> list[ReadingProgress]:
        books, _ = self._load_clippings(db_path)
        result: list[ReadingProgress] = []

        for book_data in books.values():
            result.append(
                ReadingProgress(
                    title=book_data.title,
                    author=book_data.author,
                    percent_read=None,
                    time_spent_minutes=None,
                    last_read=(
                        book_data.last_date.isoformat()
                        if book_data.last_date
                        else None
                    ),
                    read_status=None,
                    source=self.name,
                )
            )

        result.sort(key=lambda r: r.last_read or "", reverse=True)
        effective_limit = limit if limit is not None else self.DEFAULT_LIMIT
        return result[:effective_limit]

    def get_book_details(
        self,
        book_title: str | None = None,
        content_id: str | None = None,
        db_path: str | None = None,
    ) -> Book | None:
        if not book_title and not content_id:
            raise ValueError("Provide either book_title or content_id.")

        books, _ = self._load_clippings(db_path)
        search = (book_title or content_id or "").lower()

        for book_data in books.values():
            if search in book_data.title.lower():
                annotation_count = sum(
                    1
                    for e in book_data.entries
                    if e.clip_type in ("highlight", "note")
                )
                return Book(
                    title=book_data.title,
                    author=book_data.author,
                    source=self.name,
                    annotation_count=annotation_count,
                    last_read=(
                        book_data.last_date.isoformat()
                        if book_data.last_date
                        else None
                    ),
                )

        return None
