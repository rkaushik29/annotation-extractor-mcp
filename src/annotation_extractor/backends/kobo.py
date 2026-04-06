"""Kobo eReader backend.

Reads highlights, annotations, books, and reading progress from
a Kobo eReader's KoboReader.sqlite database.
"""

import os
import platform
import sqlite3
from pathlib import Path

from annotation_extractor.backends.base import EReaderBackend
from annotation_extractor.models import Annotation, Book, ReadingProgress


class KoboBackend(EReaderBackend):
    _VALID_DB_NAMES = {"KoboReader.sqlite"}

    name = "kobo"

    # ------------------------------------------------------------------
    # Detection & connection
    # ------------------------------------------------------------------

    def detect(self) -> str | None:
        candidates: list[Path] = []
        system = platform.system()

        if system == "Darwin":
            volumes = Path("/Volumes")
            if volumes.exists():
                for vol in volumes.iterdir():
                    candidate = vol / ".kobo" / "KoboReader.sqlite"
                    if candidate.exists():
                        candidates.append(candidate)
        elif system == "Linux":
            for base in [Path("/media"), Path("/mnt"), Path("/run/media")]:
                if not base.exists():
                    continue
                # Only check two levels deep (user/device) to avoid
                # hanging on network or FUSE mounts.
                for user_dir in base.iterdir():
                    for device_dir in user_dir.iterdir():
                        candidate = device_dir / ".kobo" / "KoboReader.sqlite"
                        if candidate.exists():
                            candidates.append(candidate)
        elif system == "Windows":
            import string
            for letter in string.ascii_uppercase:
                candidate = Path(f"{letter}:") / ".kobo" / "KoboReader.sqlite"
                if candidate.exists():
                    candidates.append(candidate)

        return str(candidates[0]) if candidates else None

    @classmethod
    def _validate_db_path(cls, p: Path) -> None:
        """Ensure the path points to a recognised Kobo database file."""
        if p.name not in cls._VALID_DB_NAMES:
            raise ValueError(
                f"Path must point to a Kobo database file "
                f"({', '.join(cls._VALID_DB_NAMES)}), got: {p.name}"
            )

    def _resolve_path(self, db_path: str | None) -> Path:
        if db_path:
            p = Path(db_path).resolve()
            self._validate_db_path(p)
            if p.exists():
                return p
            raise FileNotFoundError(f"Database not found at {p}")

        env = os.environ.get("KOBO_DB_PATH")
        if env:
            p = Path(env).resolve()
            self._validate_db_path(p)
            if p.exists():
                return p
            raise FileNotFoundError(f"KOBO_DB_PATH set but not found: {p}")

        detected = self.detect()
        if detected:
            return Path(detected)

        raise FileNotFoundError(
            "Could not find KoboReader.sqlite. "
            "Connect your Kobo via USB or set KOBO_DB_PATH."
        )

    def _connect(self, db_path: str | None = None) -> sqlite3.Connection:
        path = self._resolve_path(db_path)
        uri = f"file:{path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    def list_books(
        self,
        db_path: str | None = None,
        with_annotations_only: bool = True,
        limit: int | None = None,
    ) -> list[Book]:
        conn = self._connect(db_path)
        try:
            if with_annotations_only:
                query = """
                    SELECT
                        c.ContentID as content_id,
                        c.Title as title,
                        c.Attribution as author,
                        c.ISBN as isbn,
                        c.Publisher as publisher,
                        c.DateLastRead as date_last_read,
                        c.ReadStatus as read_status,
                        ROUND(c.TimeSpentReading / 60.0, 1) as time_spent_minutes,
                        COUNT(b.BookmarkID) as annotation_count
                    FROM content c
                    INNER JOIN Bookmark b ON b.VolumeID = c.ContentID
                    WHERE c.ContentType = 6
                    GROUP BY c.ContentID
                    ORDER BY c.DateLastRead DESC
                """
            else:
                query = """
                    SELECT
                        c.ContentID as content_id,
                        c.Title as title,
                        c.Attribution as author,
                        c.ISBN as isbn,
                        c.Publisher as publisher,
                        c.DateLastRead as date_last_read,
                        c.ReadStatus as read_status,
                        ROUND(c.TimeSpentReading / 60.0, 1) as time_spent_minutes,
                        (SELECT COUNT(*) FROM Bookmark b
                         WHERE b.VolumeID = c.ContentID) as annotation_count
                    FROM content c
                    WHERE c.ContentType = 6
                      AND c.Accessibility = 1
                    ORDER BY c.DateLastRead DESC
                """

            effective_limit = limit if limit is not None else self.DEFAULT_LIMIT
            query += f" LIMIT {effective_limit}"

            rows = conn.execute(query).fetchall()
            return [
                Book(
                    title=row["title"],
                    author=row["author"],
                    source=self.name,
                    content_id=row["content_id"],
                    isbn=row["isbn"],
                    publisher=row["publisher"],
                    annotation_count=row["annotation_count"],
                    last_read=row["date_last_read"],
                    time_spent_minutes=row["time_spent_minutes"],
                    read_status=row["read_status"],
                )
                for row in rows
            ]
        finally:
            conn.close()

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

        conn = self._connect(db_path)
        try:
            query = """
                SELECT
                    b.Text as highlighted_text,
                    b.Annotation as note,
                    COALESCE(c_chapter.Title, b.ContentID) as chapter,
                    b.ChapterProgress as chapter_progress,
                    b.DateCreated as date_created,
                    b.DateModified as date_modified,
                    c_book.Title as book_title,
                    c_book.Attribution as author,
                    b.Type as bookmark_type
                FROM Bookmark b
                INNER JOIN content c_book
                    ON b.VolumeID = c_book.ContentID
                    AND c_book.ContentType = 6
                LEFT JOIN content c_chapter
                    ON c_chapter.ContentID = b.ContentID
                WHERE 1=1
            """
            params: list = []

            if content_id:
                query += " AND b.VolumeID = ?"
                params.append(content_id)
            elif book_title:
                query += " AND c_book.Title LIKE ?"
                params.append(f"%{book_title}%")

            if highlights_only:
                query += " AND b.Text IS NOT NULL AND b.Text != ''"
                query += " AND (b.Annotation IS NULL OR b.Annotation = '')"
            elif notes_only:
                query += " AND b.Annotation IS NOT NULL AND b.Annotation != ''"

            query += " ORDER BY b.ContentID, b.ChapterProgress, b.DateCreated"

            effective_limit = limit if limit is not None else self.DEFAULT_LIMIT
            query += f" LIMIT {effective_limit}"

            rows = conn.execute(query, params).fetchall()
            return [
                Annotation(
                    book_title=row["book_title"],
                    author=row["author"],
                    highlighted_text=row["highlighted_text"],
                    source=self.name,
                    note=row["note"],
                    chapter=row["chapter"],
                    chapter_progress=row["chapter_progress"],
                    date_created=row["date_created"],
                    date_modified=row["date_modified"],
                    bookmark_type=str(row["bookmark_type"]) if row["bookmark_type"] is not None else None,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def search_annotations(
        self,
        query: str,
        db_path: str | None = None,
        limit: int | None = None,
    ) -> list[Annotation]:
        conn = self._connect(db_path)
        try:
            effective_limit = limit if limit is not None else self.DEFAULT_LIMIT
            sql = f"""
                SELECT
                    b.Text as highlighted_text,
                    b.Annotation as note,
                    COALESCE(c_chapter.Title, b.ContentID) as chapter,
                    b.ChapterProgress as chapter_progress,
                    b.DateCreated as date_created,
                    b.DateModified as date_modified,
                    c_book.Title as book_title,
                    c_book.Attribution as author
                FROM Bookmark b
                INNER JOIN content c_book
                    ON b.VolumeID = c_book.ContentID
                    AND c_book.ContentType = 6
                LEFT JOIN content c_chapter
                    ON c_chapter.ContentID = b.ContentID
                WHERE (b.Text LIKE ? OR b.Annotation LIKE ?)
                ORDER BY c_book.Title, b.ChapterProgress
                LIMIT {effective_limit}
            """
            pattern = f"%{query}%"
            rows = conn.execute(sql, [pattern, pattern]).fetchall()
            return [
                Annotation(
                    book_title=row["book_title"],
                    author=row["author"],
                    highlighted_text=row["highlighted_text"],
                    source=self.name,
                    note=row["note"],
                    chapter=row["chapter"],
                    chapter_progress=row["chapter_progress"],
                    date_created=row["date_created"],
                    date_modified=row["date_modified"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_reading_progress(
        self,
        db_path: str | None = None,
        limit: int | None = None,
    ) -> list[ReadingProgress]:
        conn = self._connect(db_path)
        try:
            effective_limit = limit if limit is not None else self.DEFAULT_LIMIT
            sql = f"""
                SELECT
                    c.Title as title,
                    c.Attribution as author,
                    ROUND(c.___PercentRead * 100, 1) as percent_read,
                    ROUND(c.TimeSpentReading / 60.0, 1) as time_spent_minutes,
                    c.DateLastRead as date_last_read,
                    c.ReadStatus as read_status
                FROM content c
                WHERE c.ContentType = 6
                  AND c.Accessibility = 1
                  AND c.ReadStatus > 0
                ORDER BY c.DateLastRead DESC
                LIMIT {effective_limit}
            """
            rows = conn.execute(sql).fetchall()
            return [
                ReadingProgress(
                    title=row["title"],
                    author=row["author"],
                    percent_read=row["percent_read"],
                    time_spent_minutes=row["time_spent_minutes"],
                    last_read=row["date_last_read"],
                    read_status=row["read_status"],
                    source=self.name,
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_book_details(
        self,
        book_title: str | None = None,
        content_id: str | None = None,
        db_path: str | None = None,
    ) -> Book | None:
        if not book_title and not content_id:
            raise ValueError("Provide either book_title or content_id.")

        conn = self._connect(db_path)
        try:
            sql = """
                SELECT
                    c.ContentID as content_id,
                    c.Title as title,
                    c.Subtitle as subtitle,
                    c.Attribution as author,
                    c.ISBN as isbn,
                    c.Publisher as publisher,
                    c.Description as description,
                    c.Language as language,
                    c.Series as series,
                    c.SeriesNumber as series_number,
                    c.DateLastRead as date_last_read,
                    ROUND(c.TimeSpentReading / 60.0, 1) as time_spent_minutes,
                    c.ReadStatus as read_status,
                    ROUND(c.___PercentRead * 100, 1) as percent_read,
                    (SELECT COUNT(*) FROM Bookmark b
                     WHERE b.VolumeID = c.ContentID) as annotation_count
                FROM content c
                WHERE c.ContentType = 6
            """
            params: list = []

            if content_id:
                sql += " AND c.ContentID = ?"
                params.append(content_id)
            elif book_title:
                sql += " AND c.Title LIKE ?"
                params.append(f"%{book_title}%")

            sql += " LIMIT 1"

            row = conn.execute(sql, params).fetchone()
            if not row:
                return None

            return Book(
                title=row["title"],
                author=row["author"],
                source=self.name,
                content_id=row["content_id"],
                subtitle=row["subtitle"],
                isbn=row["isbn"],
                publisher=row["publisher"],
                description=row["description"],
                language=row["language"],
                series=row["series"],
                series_number=row["series_number"],
                annotation_count=row["annotation_count"],
                last_read=row["date_last_read"],
                percent_complete=row["percent_read"],
                time_spent_minutes=row["time_spent_minutes"],
                read_status=row["read_status"],
            )
        finally:
            conn.close()
