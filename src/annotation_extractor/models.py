"""Shared data models for e-reader annotations."""

from dataclasses import dataclass, asdict


@dataclass
class Book:
    title: str
    author: str | None
    source: str
    content_id: str | None = None
    isbn: str | None = None
    publisher: str | None = None
    subtitle: str | None = None
    description: str | None = None
    language: str | None = None
    series: str | None = None
    series_number: str | None = None
    annotation_count: int = 0
    last_read: str | None = None
    percent_complete: float | None = None
    time_spent_minutes: float | None = None
    read_status: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Annotation:
    book_title: str
    author: str | None
    highlighted_text: str | None
    source: str
    note: str | None = None
    chapter: str | None = None
    chapter_progress: float | None = None
    date_created: str | None = None
    date_modified: str | None = None
    bookmark_type: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReadingProgress:
    title: str
    author: str | None
    percent_read: float | None
    time_spent_minutes: float | None
    last_read: str | None
    read_status: int | None
    source: str

    def to_dict(self) -> dict:
        return asdict(self)
