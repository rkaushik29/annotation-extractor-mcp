---
name: ereader-annotations
description: Extract highlights, annotations, notes, and reading progress from USB-connected e-readers (Kobo, Kindle, Boox). Use when the user asks about their reading highlights, book annotations, reading progress, or wants to search across their e-reader notes.
---

# E-Reader Annotation Extractor

Extract highlights, annotations, notes, and reading progress from USB-connected e-readers. Supports **Kobo**, **Kindle**, and **Boox** devices.

## Setup

Install the package:

```bash
pip install annotation-extractor
```

### MCP Server (Recommended)

The best way to use this is as an MCP server. Add it to your agent:

| Agent | Setup |
|-------|-------|
| Claude Code | `claude mcp add annotations -- annotation-extractor` |
| Claude Desktop | Add to `claude_desktop_config.json`: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |
| Cursor | Add to MCP config: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |
| Gemini CLI | Add to `~/.gemini/settings.json`: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |
| Codex | `codex --mcp-config mcp.json` with `mcp.json`: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |

Once configured, the MCP server provides these tools:

| Tool | Description |
|------|-------------|
| `list_books` | List all books, optionally filtered to those with annotations. Params: `backend_name`, `db_path`, `with_annotations_only`, `limit` |
| `get_annotations` | Get highlights and notes for a specific book by title (partial match) or content_id (exact). Params: `book_title`, `content_id`, `highlights_only`, `notes_only`, `limit` |
| `search_annotations` | Full-text search across all highlights and notes. Params: `query`, `limit` |
| `get_reading_progress` | Reading progress, time spent, and status for all books. Params: `limit` |
| `get_book_details` | Detailed metadata for a specific book. Params: `book_title`, `content_id` |

All tools accept optional `backend_name` (e.g., `"kobo"`, `"kindle"`, `"boox"`) and `db_path`. When omitted, the server auto-detects connected devices.

### Workflow

1. Call `list_books` to discover what books are available and see annotation counts
2. Use `get_annotations` with a `book_title` to retrieve highlights and notes for a specific book
3. Use `search_annotations` to search across all highlights and notes
4. Use `get_reading_progress` for an overview of reading activity
5. Use `get_book_details` for full metadata (ISBN, publisher, description, series info)

## Direct Access (Without MCP)

If your agent doesn't support MCP, you can query e-reader data directly.

### Using Python

```bash
pip install annotation-extractor
python -c "
from annotation_extractor.backends.kobo import KoboBackend
b = KoboBackend()
for book in b.list_books():
    print(f'{book.title} by {book.author} - {book.annotation_count} annotations')
"
```

Replace `KoboBackend` with `KindleBackend` or `BooxBackend` as needed (import from `annotation_extractor.backends.kindle` or `annotation_extractor.backends.boox`).

### Raw Database Access (Kobo)

Kobo stores data in a SQLite database at `.kobo/KoboReader.sqlite` on the mounted device.

- **macOS**: `/Volumes/<DeviceName>/.kobo/KoboReader.sqlite`
- **Linux**: `/media/<user>/<device>/.kobo/KoboReader.sqlite`
- **Windows**: `<DriveLetter>:\.kobo\KoboReader.sqlite`

List books with annotations:

```sql
sqlite3 -readonly /path/to/KoboReader.sqlite "
SELECT c.Title, c.Attribution, COUNT(b.BookmarkID) as annotations
FROM content c
INNER JOIN Bookmark b ON b.VolumeID = c.ContentID
WHERE c.ContentType = 6
GROUP BY c.ContentID
ORDER BY c.DateLastRead DESC;
"
```

Get highlights for a book:

```sql
sqlite3 -readonly /path/to/KoboReader.sqlite "
SELECT b.Text, b.Annotation, b.DateCreated
FROM Bookmark b
INNER JOIN content c ON b.VolumeID = c.ContentID AND c.ContentType = 6
WHERE c.Title LIKE '%BookTitle%'
ORDER BY b.ChapterProgress;
"
```

### Raw File Access (Kindle)

Kindle stores clippings at `documents/My Clippings.txt` on the mounted device. Entries are separated by `==========`. Each entry has:

```
Book Title (Author)
- Your Highlight on page X | Location Y-Z | Added on Day, Month DD, YYYY HH:MM:SS AM/PM

Highlighted text here
==========
```

### Raw File Access (Boox)

Boox exports one `.txt` file per book into an export directory. Files are named `BookTitle-annotation-YYYY-MM-DD_HH_MM_SS.txt`. Each file has a header line and annotation entries with metadata (date, page number) followed by highlighted text and optional notes.

## Environment Variables

If auto-detection doesn't find your device, point to the data source directly:

| Variable | Description |
|----------|-------------|
| `KOBO_DB_PATH` | Path to `KoboReader.sqlite` |
| `KINDLE_CLIPPINGS_PATH` | Path to `My Clippings.txt` |
| `BOOX_EXPORT_PATH` | Path to Boox annotation export directory |

## Data Model Reference

**Book**: title, author, source, content_id, isbn, publisher, subtitle, description, language, series, series_number, annotation_count, last_read, percent_complete, time_spent_minutes, read_status

**Annotation**: book_title, author, highlighted_text, source, note, chapter, chapter_progress, date_created, date_modified, bookmark_type

**ReadingProgress**: title, author, percent_read, time_spent_minutes, last_read, read_status, source

## Troubleshooting

- **Device not detected**: Ensure the e-reader is connected via USB and mounted. Set the appropriate environment variable to specify the path manually.
- **Database locked**: The Kobo database is opened in read-only mode. If you still get lock errors, copy the database file locally first.
- **Multiple devices**: Use the `backend_name` parameter to specify which e-reader to query, or `db_path` to point to a specific data source.
