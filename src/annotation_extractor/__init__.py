"""annotation-extractor: MCP server for e-reader annotations and highlights."""


def main() -> None:
    from annotation_extractor.server import main as server_main

    server_main()

__all__ = ["main"]
