"""Loader for the configured partners file."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PartnersService:
    """Loads {id: name} partner mappings from a JSON file path."""

    def __init__(self, file_path: str | None) -> None:
        self._file_path = file_path

    def load(self) -> list[dict[str, str]]:
        """Return partners as [{"id": ..., "name": ...}, ...] sorted by name.

        Returns an empty list (and logs a warning) if the path is unset,
        the file is missing, or the file is malformed.
        """
        if not self._file_path:
            return []

        path = Path(self._file_path)
        if not path.is_file():
            logger.warning("Partners file not found at %s", self._file_path)
            return []

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read partners file %s: %s", self._file_path, exc)
            return []

        if not isinstance(raw, dict):
            logger.warning("Partners file %s is not a JSON object", self._file_path)
            return []

        partners = [
            {"id": str(pid), "name": name}
            for pid, name in raw.items()
            if isinstance(name, str)
        ]
        partners.sort(key=lambda p: p["name"])
        return partners
