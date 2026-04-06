"""Abstract base class for e-reader backends."""

from abc import ABC, abstractmethod

from annotation_extractor.models import Annotation, Book, ReadingProgress


class EReaderBackend(ABC):
    """Base class that all e-reader backends must implement."""

    name: str

    @abstractmethod
    def detect(self) -> str | None:
        """Auto-detect the device/data path on this system.

        Returns the path string if found, None if this backend's
        device is not connected or available.
        """
        ...

    @abstractmethod
    def list_books(
        self,
        db_path: str | None = None,
        with_annotations_only: bool = True,
    ) -> list[Book]:
        """Return all books on the device."""
        ...

    @abstractmethod
    def get_annotations(
        self,
        book_title: str | None = None,
        content_id: str | None = None,
        db_path: str | None = None,
        highlights_only: bool = False,
        notes_only: bool = False,
    ) -> list[Annotation]:
        """Return annotations, optionally filtered by book."""
        ...

    @abstractmethod
    def search_annotations(
        self,
        query: str,
        db_path: str | None = None,
    ) -> list[Annotation]:
        """Full-text search across all annotations."""
        ...

    @abstractmethod
    def get_reading_progress(
        self,
        db_path: str | None = None,
    ) -> list[ReadingProgress]:
        """Return reading progress for all books."""
        ...

    @abstractmethod
    def get_book_details(
        self,
        book_title: str | None = None,
        content_id: str | None = None,
        db_path: str | None = None,
    ) -> Book | None:
        """Return detailed metadata for a specific book."""
        ...
