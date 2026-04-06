"""Boox eReader backend.

Reads highlights and annotations from Boox annotation export files.
Boox exports one text file per book into a directory, with filenames
like ``BookTitle-annotation-YYYY-MM-DD_HH_MM_SS.txt``.
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

# Header: Reading Notes | <<Title - Author__UUID>>
_HEADER_RE = re.compile(
    r"^Reading Notes\s*\|\s*<<(.+?)(?:\s+-\s+(.+?))?(?:__([a-zA-Z0-9-]+))?>>\s*$"
)

# Annotation metadata: Author. YYYY-MM-DD HH:MM | Page No. : 42
_ANNOTATION_META_RE = re.compile(
    r"^(.+?)\.\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*\|\s*Page No\.\s*:\s*(\d+)\s*$"
)

# Filename pattern for auto-detection
_FILENAME_RE = re.compile(
    r"^.+-annotation-\d{4}-\d{2}-\d{2}_\d{2}_\d{2}(?:_\d{2})?\.txt$"
)

_BOOX_DATE_FORMAT = "%Y-%m-%d %H:%M"


@dataclass
class _BooxAnnotation:
    book_title: str
    author: str | None
    content_id: str | None
    page: int | None
    date_added: datetime | None
    date_added_raw: str | None
    highlighted_text: str
    note: str | None


@dataclass
class _BooxBookData:
    title: str
    author: str | None
    content_id: str | None
    annotations: list[_BooxAnnotation] = field(default_factory=list)
    last_date: datetime | None = None


def _parse_boox_date(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw.strip(), _BOOX_DATE_FORMAT)
    except ValueError:
        return None


def _parse_boox_file(file_path: Path) -> _BooxBookData | None:
    """Parse a single Boox annotation export file."""
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        logger.warning("Could not read file: %s", file_path)
        return None

    lines = text.split("\n")
    if not lines:
        return None

    # Parse header
    header_line = lines[0].strip()
    header_line = header_line.lstrip("\ufeff")
    m_header = _HEADER_RE.match(header_line)
    if not m_header:
        logger.warning("Skipping file without valid Boox header: %s", file_path.name)
        return None

    book_title = m_header.group(1).strip()
    author = m_header.group(2).strip() if m_header.group(2) else None
    content_id = m_header.group(3) if m_header.group(3) else None

    book = _BooxBookData(
        title=book_title,
        author=author,
        content_id=content_id,
    )

    # Parse annotations — find metadata lines, then collect content after them
    annotation_starts: list[tuple[int, re.Match]] = []
    for i, line in enumerate(lines[1:], start=1):
        m = _ANNOTATION_META_RE.match(line.strip())
        if m:
            annotation_starts.append((i, m))

    for idx, (line_idx, m_meta) in enumerate(annotation_starts):
        date_raw = m_meta.group(2)
        date_added = _parse_boox_date(date_raw)
        page = int(m_meta.group(3))

        # Collect lines until next annotation or end of file
        if idx + 1 < len(annotation_starts):
            end_idx = annotation_starts[idx + 1][0]
        else:
            end_idx = len(lines)

        content_lines = lines[line_idx + 1 : end_idx]
        content_block = "\n".join(content_lines).strip()

        # Split content into highlighted text and optional note by blank line
        parts = re.split(r"\n\s*\n", content_block, maxsplit=1)
        highlighted_text = parts[0].strip() if parts else ""
        note = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None

        if not highlighted_text:
            continue

        ann = _BooxAnnotation(
            book_title=book_title,
            author=author,
            content_id=content_id,
            page=page,
            date_added=date_added,
            date_added_raw=date_raw,
            highlighted_text=highlighted_text,
            note=note,
        )
        book.annotations.append(ann)

        if date_added:
            if book.last_date is None or date_added > book.last_date:
                book.last_date = date_added

    return book


def _dir_has_boox_files(directory: Path) -> bool:
    """Check if a directory contains at least one Boox annotation file."""
    try:
        for f in directory.iterdir():
            if f.suffix == ".txt" and _FILENAME_RE.match(f.name):
                return True
    except OSError:
        pass
    return False


def _load_all_books(directory: Path) -> dict[str, _BooxBookData]:
    """Enumerate and parse all Boox export files in a directory."""
    books: dict[str, _BooxBookData] = {}

    for f in sorted(directory.iterdir()):
        if not f.is_file() or f.suffix != ".txt":
            continue

        book_data = _parse_boox_file(f)
        if book_data is None:
            continue

        key = f"{book_data.title.strip().lower()}||{(book_data.author or '').strip().lower()}"

        if key in books:
            # Merge annotations from duplicate exports, deduplicate
            existing = books[key]
            seen = {
                (a.page, a.highlighted_text) for a in existing.annotations
            }
            for ann in book_data.annotations:
                if (ann.page, ann.highlighted_text) not in seen:
                    existing.annotations.append(ann)
                    seen.add((ann.page, ann.highlighted_text))
            if book_data.last_date:
                if existing.last_date is None or book_data.last_date > existing.last_date:
                    existing.last_date = book_data.last_date
            if not existing.content_id and book_data.content_id:
                existing.content_id = book_data.content_id
        else:
            books[key] = book_data

    return books


class BooxBackend(EReaderBackend):
    name = "boox"

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
                    for subdir in ["boox-export", "Export", "note", "Notes"]:
                        export_dir = vol / subdir
                        if export_dir.is_dir() and _dir_has_boox_files(export_dir):
                            candidates.append(export_dir)
        elif system == "Linux":
            for base in [Path("/media"), Path("/mnt"), Path("/run/media")]:
                if not base.exists():
                    continue
                for user_dir in base.iterdir():
                    for device_dir in user_dir.iterdir():
                        for subdir in ["boox-export", "Export", "note", "Notes"]:
                            export_dir = device_dir / subdir
                            if export_dir.is_dir() and _dir_has_boox_files(export_dir):
                                candidates.append(export_dir)
        elif system == "Windows":
            import string

            for letter in string.ascii_uppercase:
                for subdir in ["boox-export", "Export", "note", "Notes"]:
                    export_dir = Path(f"{letter}:") / subdir
                    if export_dir.is_dir() and _dir_has_boox_files(export_dir):
                        candidates.append(export_dir)

        return str(candidates[0]) if candidates else None

    def _resolve_path(self, db_path: str | None) -> Path:
        if db_path:
            p = Path(db_path).resolve()
            # If user passed a single file, use its parent directory
            if p.is_file():
                p = p.parent
            if p.is_dir():
                return p
            raise FileNotFoundError(f"Boox export directory not found at {p}")

        env = os.environ.get("BOOX_EXPORT_PATH")
        if env:
            p = Path(env).resolve()
            if p.is_dir():
                return p
            raise FileNotFoundError(
                f"BOOX_EXPORT_PATH set but not found: {p}"
            )

        detected = self.detect()
        if detected:
            return Path(detected)

        raise FileNotFoundError(
            "Could not find Boox export directory. "
            "Connect your Boox device via USB or set BOOX_EXPORT_PATH."
        )

    def _load_books(
        self, db_path: str | None
    ) -> dict[str, _BooxBookData]:
        directory = self._resolve_path(db_path)
        return _load_all_books(directory)

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def list_books(
        self,
        db_path: str | None = None,
        with_annotations_only: bool = True,
        limit: int | None = None,
    ) -> list[Book]:
        books = self._load_books(db_path)
        result: list[Book] = []

        for book_data in books.values():
            annotation_count = len(book_data.annotations)
            if with_annotations_only and annotation_count == 0:
                continue

            result.append(
                Book(
                    title=book_data.title,
                    author=book_data.author,
                    source=self.name,
                    content_id=book_data.content_id,
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

        books = self._load_books(db_path)
        search_title = (book_title or "").lower() if book_title else None
        search_id = content_id

        matched_annotations: list[_BooxAnnotation] = []
        for book_data in books.values():
            if search_id and book_data.content_id == search_id:
                matched_annotations.extend(book_data.annotations)
            elif search_title and search_title in book_data.title.lower():
                matched_annotations.extend(book_data.annotations)

        annotations = _build_annotations(matched_annotations, self.name)

        if highlights_only:
            annotations = [
                a for a in annotations if a.highlighted_text and not a.note
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
        books = self._load_books(db_path)
        all_anns: list[_BooxAnnotation] = []
        for book_data in books.values():
            all_anns.extend(book_data.annotations)

        annotations = _build_annotations(all_anns, self.name)
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
        books = self._load_books(db_path)
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

        books = self._load_books(db_path)
        search_title = (book_title or "").lower() if book_title else None
        search_id = content_id

        for book_data in books.values():
            if search_id and book_data.content_id == search_id:
                pass
            elif search_title and search_title in book_data.title.lower():
                pass
            else:
                continue

            return Book(
                title=book_data.title,
                author=book_data.author,
                source=self.name,
                content_id=book_data.content_id,
                annotation_count=len(book_data.annotations),
                last_read=(
                    book_data.last_date.isoformat()
                    if book_data.last_date
                    else None
                ),
            )

        return None


def _build_annotations(
    entries: list[_BooxAnnotation], source: str
) -> list[Annotation]:
    """Convert internal Boox annotations to shared Annotation objects."""
    annotations: list[Annotation] = []

    for entry in entries:
        annotations.append(
            Annotation(
                book_title=entry.book_title,
                author=entry.author,
                highlighted_text=entry.highlighted_text or None,
                source=source,
                note=entry.note,
                date_created=(
                    entry.date_added.isoformat()
                    if entry.date_added
                    else entry.date_added_raw
                ),
                bookmark_type="highlight",
            )
        )

    annotations.sort(key=lambda a: a.date_created or "")
    return annotations
