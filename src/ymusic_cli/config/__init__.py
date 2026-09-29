"""Configuration management for YMusic CLI.

Ensures user tokens and configs are stored strictly in user-profile directories
(Linux/macOS: ~/.config/ymusic-cli, Windows: %APPDATA%/ymusic-cli) and NEVER
in build, dist, or project workspace folders.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


def get_default_config_dir() -> Path:
    """Return standard user configuration directory based on OS.

    - Windows: %APPDATA%/ymusic-cli
    - Linux/macOS: $XDG_CONFIG_HOME/ymusic-cli (default: ~/.config/ymusic-cli)
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "ymusic-cli"
        return Path.home() / "AppData" / "Roaming" / "ymusic-cli"

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "ymusic-cli"
    return Path.home() / ".config" / "ymusic-cli"


def get_default_cache_dir() -> Path:
    """Return standard user cache directory based on OS.

    - Windows: %LOCALAPPDATA%/ymusic-cli
    - Linux/macOS: $XDG_CACHE_HOME/ymusic-cli (default: ~/.cache/ymusic-cli)
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "ymusic-cli"
        return Path.home() / "AppData" / "Local" / "ymusic-cli"

    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / "ymusic-cli"
    return Path.home() / ".cache" / "ymusic-cli"


def get_default_config_file() -> Path:
    """Return standard path to config.json."""
    return get_default_config_dir() / "config.json"


# Global defaults for backwards compatibility
DEFAULT_CONFIG_DIR = get_default_config_dir()
DEFAULT_CONFIG_FILE = get_default_config_file()


def _is_unsafe_path(path: Path) -> bool:
    """Check if a path points to a build, dist, repository or temporary bundle folder."""
    resolved = path.resolve()
    parts = set(resolved.parts)
    unsafe_dirs = {"build", "dist", ".git", ".venv", "venv", "__pycache__"}
    if unsafe_dirs & parts:
        return True
    # PyInstaller temporary extraction directory
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and Path(meipass).resolve() in resolved.parents:
        return True
    return False


@dataclass
class Config:
    """Application configuration stored as JSON."""

    token: str = ""
    volume: int = 70
    quality: str = "high"  # low, medium, high, lossless
    cache_dir: str = ""

    def __post_init__(self) -> None:
        if not self.cache_dir:
            self.cache_dir = str(get_default_cache_dir())

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from disk, checking env vars and creating defaults if missing."""
        target_path = path or get_default_config_file()

        # Reject loading token from build / dist / bundle folders
        if _is_unsafe_path(target_path):
            target_path = get_default_config_file()

        cfg: Config | None = None
        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    valid = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
                    cfg = cls(**valid)
            except (json.JSONDecodeError, OSError):
                pass

        if cfg is None:
            cfg = cls()

        # Check environment variable overrides for token
        env_token = os.environ.get("YANDEX_MUSIC_TOKEN") or os.environ.get("YMUSIC_TOKEN")
        if env_token and not cfg.token:
            cfg.token = env_token.strip()

        # Ensure config file exists in the safe default user directory
        if not target_path.exists():
            try:
                cfg.save(target_path)
            except OSError:
                pass

        return cfg

    def save(self, path: Path | None = None) -> None:
        """Persist config to disk in a secure user-profile location."""
        target_path = path or get_default_config_file()

        # Disallow saving credentials into build, dist, or unsafe folders
        if _is_unsafe_path(target_path):
            target_path = get_default_config_file()

        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2, ensure_ascii=False)

            # Restrict file permissions to current user only on POSIX systems
            if sys.platform != "win32":
                try:
                    os.chmod(target_path, 0o600)
                except OSError:
                    pass
        except OSError:
            pass

    @property
    def is_authenticated(self) -> bool:
        return bool(self.token)
