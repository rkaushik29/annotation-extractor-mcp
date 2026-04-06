"""Backend registry — discovery, auto-detection, and routing."""

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
        if p.is_dir():
            for b in _ALL_BACKENDS:
                if b.name == "boox":
                    return b
        if db_path.endswith(".txt"):
            for b in _ALL_BACKENDS:
                if b.name == "kindle":
                    return b
        if db_path.endswith(".sqlite"):
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
