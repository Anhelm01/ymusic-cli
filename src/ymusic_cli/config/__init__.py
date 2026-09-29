"""Configuration management for YMusic CLI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "ymusic-cli"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"


@dataclass
class Config:
    """Application configuration stored as JSON."""

    token: str = ""
    volume: int = 70
    quality: str = "high"  # low, medium, high, lossless
    cache_dir: str = str(Path.home() / ".cache" / "ymusic-cli")

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from disk, creating defaults if missing or corrupted."""
        path = path or DEFAULT_CONFIG_FILE
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
                    return cls(**valid)
            except (json.JSONDecodeError, OSError):
                pass
        cfg = cls()
        try:
            cfg.save(path)
        except OSError:
            pass
        return cfg

    def save(self, path: Path | None = None) -> None:
        """Persist config to disk."""
        path = path or DEFAULT_CONFIG_FILE
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    @property
    def is_authenticated(self) -> bool:
        return bool(self.token)
