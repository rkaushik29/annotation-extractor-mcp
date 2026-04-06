"""
annotation-extractor: MCP server for e-reader annotations and highlights.

Exposes highlights, notes, books, and reading progress from USB-connected
e-readers via the Model Context Protocol. Currently supports Kobo, with
an extensible backend architecture for Kindle and others.
"""

from typing import Optional

from mcp.server.fastmcp import FastMCP

from annotation_extractor.registry import detect_backends, get_backend

mcp = FastMCP(
    "annotation-extractor",
    instructions=(
        "Provides access to highlights, annotations, books, and reading progress "
        "from e-readers connected via USB. Supports Kobo, Kindle, and Boox. "
        "Use list_books to discover available books, then "
        "get_annotations to retrieve highlights and notes for a specific book."
    ),
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_books(
    backend_name: Optional[str] = None,
    db_path: Optional[str] = None,
    with_annotations_only: bool = True,
    limit: Optional[int] = None,
) -> list[dict]:
    """List all books on the connected e-reader.

    Args:
        backend_name: Which e-reader backend to use (e.g. "kobo").
                      Auto-detected if not provided.
        db_path: Optional explicit path to the e-reader database.
                 If not provided, auto-detects the mounted device.
        with_annotations_only: If True, only return books that have
                               at least one highlight or annotation.
        limit: Maximum number of results to return. Defaults to 500.

    Returns:
        List of books with title, author, content_id, annotation_count,
        last_read, time_spent_minutes, read_status, and source.
    """
    backend = get_backend(backend_name, db_path)
    books = backend.list_books(db_path=db_path, with_annotations_only=with_annotations_only, limit=limit)
    return [b.to_dict() for b in books]


@mcp.tool()
def get_annotations(
    book_title: Optional[str] = None,
    content_id: Optional[str] = None,
    backend_name: Optional[str] = None,
    db_path: Optional[str] = None,
    highlights_only: bool = False,
    notes_only: bool = False,
    limit: Optional[int] = None,
) -> list[dict]:
    """Get highlights and annotations for a specific book.

    Provide either book_title (partial match) or content_id (exact match).

    Args:
        book_title: Partial title to search for (case-insensitive).
        content_id: Exact content ID from list_books.
        backend_name: Which e-reader backend to use. Auto-detected if omitted.
        db_path: Optional explicit path to the e-reader database.
        highlights_only: Only return highlights (no user notes).
        notes_only: Only return entries that have a user-written note.
        limit: Maximum number of results to return. Defaults to 500.

    Returns:
        List of annotations with highlighted_text, note, chapter,
        chapter_progress, date_created, book_title, author, and source.
    """
    backend = get_backend(backend_name, db_path)
    annotations = backend.get_annotations(
        book_title=book_title,
        content_id=content_id,
        db_path=db_path,
        highlights_only=highlights_only,
        notes_only=notes_only,
        limit=limit,
    )
    return [a.to_dict() for a in annotations]


@mcp.tool()
def search_annotations(
    query: str,
    backend_name: Optional[str] = None,
    db_path: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """Search across all highlights and notes on the e-reader.

    Searches both highlighted text and user-written notes.

    Args:
        query: Text to search for (case-insensitive, partial match).
        backend_name: Which e-reader backend to use. Auto-detected if omitted.
        db_path: Optional explicit path to the e-reader database.
        limit: Maximum number of results to return. Defaults to 500.

    Returns:
        Matching annotations with book context.
    """
    backend = get_backend(backend_name, db_path)
    annotations = backend.search_annotations(query=query, db_path=db_path, limit=limit)
    return [a.to_dict() for a in annotations]


@mcp.tool()
def get_reading_progress(
    backend_name: Optional[str] = None,
    db_path: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """Get reading progress for all books on the e-reader.

    Args:
        backend_name: Which e-reader backend to use. Auto-detected if omitted.
        db_path: Optional explicit path to the e-reader database.
        limit: Maximum number of results to return. Defaults to 500.

    Returns:
        List of books with title, author, percent_read,
        time_spent_minutes, last_read, read_status, and source.
    """
    backend = get_backend(backend_name, db_path)
    progress = backend.get_reading_progress(db_path=db_path, limit=limit)
    return [p.to_dict() for p in progress]


@mcp.tool()
def get_book_details(
    book_title: Optional[str] = None,
    content_id: Optional[str] = None,
    backend_name: Optional[str] = None,
    db_path: Optional[str] = None,
) -> dict | None:
    """Get detailed metadata for a specific book.

    Args:
        book_title: Partial title to search for (case-insensitive).
        content_id: Exact content ID from list_books.
        backend_name: Which e-reader backend to use. Auto-detected if omitted.
        db_path: Optional explicit path to the e-reader database.

    Returns:
        Book metadata including title, author, isbn, publisher,
        description, language, series, percent_complete, and more.
    """
    backend = get_backend(backend_name, db_path)
    book = backend.get_book_details(
        book_title=book_title,
        content_id=content_id,
        db_path=db_path,
    )
    return book.to_dict() if book else None


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("annotations://status")
def status() -> str:
    """Check which e-readers are connected and return basic stats."""
    found = detect_backends()
    if not found:
        return "No e-readers detected. Connect a device via USB."

    lines = []
    for backend, path in found:
        lines.append(f"{backend.name}: connected at {path}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main():
    mcp.run()


if __name__ == "__main__":
    main()
