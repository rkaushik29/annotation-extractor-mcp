"""Backend registry — discovery, auto-detection, and routing."""

import re
from pathlib import Path

from annotation_extractor.backends.base import EReaderBackend
from annotation_extractor.backends.boox import BooxBackend
from annotation_extractor.backends.kindle import KindleBackend
from annotation_extractor.backends.kobo import KoboBackend

_ALL_BACKENDS: list[EReaderBackend] = [
    KoboBackend(),
    KindleBackend(),
    BooxBackend(),
]

_BOOX_EXPORT_TXT_RE = re.compile(
    r"^.+-annotation-\d{4}-\d{2}-\d{2}_\d{2}_\d{2}(?:_\d{2})?\.txt$",
    re.IGNORECASE,
)


def detect_backends() -> list[tuple[EReaderBackend, str]]:
    """Return (backend, detected_path) for all connected e-readers."""
    found = []
    for backend in _ALL_BACKENDS:
        path = backend.detect()
        if path is not None:
            found.append((backend, path))
    return found


def get_backend(
    backend_name: str | None = None,
    db_path: str | None = None,
) -> EReaderBackend:
    """Resolve a single backend to use.

    Priority: explicit backend_name > auto-detect.
    db_path is passed through to the backend methods, not used for selection.
    """
    if backend_name:
        for b in _ALL_BACKENDS:
            if b.name == backend_name:
                return b
        names = [b.name for b in _ALL_BACKENDS]
        raise ValueError(f"Unknown backend: {backend_name!r}. Available: {names}")

    if db_path:
        # Infer backend from path type
        p = Path(db_path)

        if p.is_file():
            name = p.name
            lower_name = name.lower()

            if lower_name == "my clippings.txt":
                for b in _ALL_BACKENDS:
                    if b.name == "kindle":
                        return b

            if lower_name.endswith(".sqlite"):
                for b in _ALL_BACKENDS:
                    if b.name == "kobo":
                        return b

            if lower_name.endswith(".txt"):
                if _BOOX_EXPORT_TXT_RE.match(name):
                    for b in _ALL_BACKENDS:
                        if b.name == "boox":
                            return b
                for b in _ALL_BACKENDS:
                    if b.name == "kindle":
                        return b

            if lower_name.endswith(".zip"):
                for b in _ALL_BACKENDS:
                    if b.name == "boox":
                        return b

        if p.is_dir():
            if p.name == ".notebooks" or (p / ".notebooks").is_dir():
                for b in _ALL_BACKENDS:
                    if b.name == "kindle":
                        return b

            if p.name.endswith("!!notebook") and p.parent.name == ".notebooks":
                for b in _ALL_BACKENDS:
                    if b.name == "kindle":
                        return b

            if (p / "documents" / "My Clippings.txt").is_file() or (p / "My Clippings.txt").is_file():
                for b in _ALL_BACKENDS:
                    if b.name == "kindle":
                        return b

            for b in _ALL_BACKENDS:
                if b.name == "boox":
                    return b

        lower_db_path = db_path.lower()
        if lower_db_path.endswith(".txt"):
            if _BOOX_EXPORT_TXT_RE.match(p.name):
                for b in _ALL_BACKENDS:
                    if b.name == "boox":
                        return b
            for b in _ALL_BACKENDS:
                if b.name == "kindle":
                    return b

        if lower_db_path.endswith(".sqlite"):
            for b in _ALL_BACKENDS:
                if b.name == "kobo":
                    return b

        return _ALL_BACKENDS[0]

    results = detect_backends()
    if not results:
        raise RuntimeError(
            "No e-reader detected. Connect a device via USB, "
            "set KOBO_DB_PATH / KINDLE_CLIPPINGS_PATH / BOOX_EXPORT_PATH, "
            "or provide backend_name and db_path."
        )
    if len(results) > 1:
        names = [r[0].name for r in results]
        raise RuntimeError(
            f"Multiple readers detected: {names}. "
            "Specify backend_name to disambiguate."
        )
    return results[0][0]
