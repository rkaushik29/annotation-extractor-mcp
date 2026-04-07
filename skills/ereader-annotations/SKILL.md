---
name: ereader-annotations
description: Extract highlights, annotations, notes, and reading progress from USB-connected e-readers (Kobo, Kindle, Boox). Use when the user asks about their reading highlights, book annotations, reading progress, or wants to search across their e-reader notes.
---

# E-Reader Annotation Extractor

When the user asks about their reading highlights, annotations, notes, or reading progress from an e-reader, follow these steps.

## Step 1: Check if the MCP server is already available

Look for tools named `list_books`, `get_annotations`, `search_annotations`, `get_reading_progress`, or `get_book_details` in your available tools. If they exist, skip to **Step 4: Use the tools**.

## Step 2: Install the package

Run:

```bash
pip install annotation-extractor
```

If `pip` is not available, try `uv pip install annotation-extractor` or `pipx install annotation-extractor`.

## Step 3: Set up the MCP server

Tell the user to add the MCP server to their agent. Detect which agent you are and give the appropriate command:

| Agent | Command to give the user |
|-------|--------------------------|
| Claude Code | `claude mcp add annotations -- annotation-extractor` |
| Claude Desktop | Add to `claude_desktop_config.json`: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |
| Cursor | Add to MCP config: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |
| Gemini CLI | Add to `~/.gemini/settings.json`: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |
| Codex | `codex --mcp-config mcp.json` with `mcp.json`: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |

If you can run the setup command yourself (e.g. in Claude Code), do so. Otherwise, show the user the exact command and ask them to run it, then restart the session.

**Important**: After MCP setup, the tools won't be available until the session is restarted. If you just set up the MCP server, tell the user to restart and try again. In the meantime, use the direct access method below to answer their question now.

## Step 4: Use the tools

If the MCP tools are available, use them in this order:

1. Call `list_books` to discover available books and annotation counts
2. Use `get_annotations` with `book_title` (partial match) to get highlights and notes
3. Use `search_annotations` with a `query` to search across all highlights
4. Use `get_reading_progress` for reading activity overview
5. Use `get_book_details` for full metadata (ISBN, publisher, series)

All tools accept optional `backend_name` (`"kobo"`, `"kindle"`, `"boox"`) and `db_path`. When omitted, connected devices are auto-detected.

## Fallback: Direct access (if MCP is not available)

If you cannot set up MCP or need to answer the user's question right now, use these methods:

### Option A: Python (preferred)

```bash
pip install annotation-extractor
python -c "
from annotation_extractor.backends.kobo import KoboBackend
b = KoboBackend()
for book in b.list_books():
    print(f'{book.title} by {book.author} - {book.annotation_count} annotations')
"
```

Replace `KoboBackend` with `KindleBackend` (from `annotation_extractor.backends.kindle`) or `BooxBackend` (from `annotation_extractor.backends.boox`) as needed.

To get annotations for a specific book:

```bash
python -c "
from annotation_extractor.backends.kobo import KoboBackend
b = KoboBackend()
for a in b.get_annotations(book_title='BOOK_TITLE_HERE'):
    print(f'[{a.chapter}] {a.highlighted_text}')
    if a.note: print(f'  Note: {a.note}')
"
```

### Option B: Raw SQLite (Kobo only, no install needed)

If Python package installation is not possible, query the Kobo database directly. The database is at `.kobo/KoboReader.sqlite` on the mounted device:

- **macOS**: `/Volumes/<DeviceName>/.kobo/KoboReader.sqlite`
- **Linux**: `/media/<user>/<device>/.kobo/KoboReader.sqlite`
- **Windows**: `<DriveLetter>:\.kobo\KoboReader.sqlite`

### Raw SQLite queries (Kobo)

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

### Raw file access (Kindle)

Kindle stores clippings at `documents/My Clippings.txt` on the mounted device. Entries are separated by `==========` with format: title line, metadata line, blank line, highlighted text.

### Raw file access (Boox)

Boox exports one `.txt` file per book into a directory (`boox-export/`, `Export/`, `note/`, or `Notes/` on the device). Files are named `BookTitle-annotation-YYYY-MM-DD_HH_MM_SS.txt`.

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
