# annotation-extractor

MCP server for extracting annotations, highlights, and reading progress from e-readers.

Supports **Kobo**, **Kindle**, and **Boox**.

## Install

```bash
pip install annotation-extractor
```

### As an Agent Skill

Install as a reusable skill for any AI coding agent via [skills.sh](https://skills.sh):

```bash
npx skills add rkaushik29/annotation-extractor-mcp
```

Or from source:

```bash
git clone https://github.com/rkaushik29/annotation-extractor-mcp.git
cd annotation-extractor
pip install -e .
```

## Usage

Connect your e-reader via USB, add the MCP server to your agent, and start asking questions about your reading.

| Client | Setup |
|--------|-------|
| Claude Code | `claude mcp add annotations -- annotation-extractor` |
| Claude Desktop | Add to `claude_desktop_config.json`: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |
| OpenClaw | `openclaw mcp add annotations -- annotation-extractor` |
| Gemini CLI | Add to `~/.gemini/settings.json`: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |
| Codex | `codex --mcp-config mcp.json` with `mcp.json`: `{"mcpServers": {"annotations": {"command": "annotation-extractor"}}}` |

### Try it out

Once the MCP is connected and your e-reader is plugged in, try asking your agent:

> "What are my highlights from the last book I read?"

> "Search my annotations for anything about consciousness"

> "Show me all the notes I took while reading Neuromancer"

### Environment variables

If auto-detection doesn't find your device, you can point to the data source directly:

```bash
KOBO_DB_PATH=/path/to/KoboReader.sqlite annotation-extractor
KINDLE_CLIPPINGS_PATH=/path/to/My\ Clippings.txt annotation-extractor
BOOX_EXPORT_PATH=/path/to/boox-export annotation-extractor
```

## Supported e-readers

| Reader | Data source |
|--------|-------------|
| Kobo | `.kobo/KoboReader.sqlite` via USB |
| Kindle | `My Clippings.txt` via USB |
| Boox | Annotation export directory (one `.txt` file per book) via USB |

## Tools

| Tool | Description |
|------|-------------|
| `list_books` | List all books, optionally filtered to those with annotations |
| `get_annotations` | Get highlights and notes for a specific book (by title or ID) |
| `search_annotations` | Full-text search across all highlights and notes |
| `get_reading_progress` | Reading progress, time spent, and status for all books |
| `get_book_details` | Detailed metadata for a specific book |

All tools accept optional `backend_name` (e.g., `"kobo"`, `"kindle"`, `"boox"`) and `db_path` parameters. When omitted, the server auto-detects connected devices.

## Adding a new backend

1. Create `src/annotation_extractor/backends/yourreader.py` implementing `EReaderBackend`
2. Add your backend to `_ALL_BACKENDS` in `registry.py`
3. No changes needed to `server.py` or `models.py`

## Development

```bash
git clone https://github.com/rohitkaushik/annotation-extractor.git
cd annotation-extractor
pip install -e ".[dev]"
pytest
```

## License

MIT
