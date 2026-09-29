"""Tests for config paths, token security, and build safety."""

import os
from pathlib import Path
from unittest.mock import patch

from ymusic_cli.auth import copy_to_clipboard
from ymusic_cli.config import (
    Config,
    _is_unsafe_path,
)


def test_unsafe_paths():
    """Verify that build, dist, and git directories are recognized as unsafe."""
    assert _is_unsafe_path(Path("/home/user/project/build/config.json")) is True
    assert _is_unsafe_path(Path("/home/user/project/dist/config.json")) is True
    assert _is_unsafe_path(Path("/home/user/project/.git/config.json")) is True
    assert _is_unsafe_path(Path("/home/user/project/.venv/config.json")) is True

    # Safe user profile paths
    safe_path = Path.home() / ".config" / "ymusic-cli" / "config.json"
    assert _is_unsafe_path(safe_path) is False


def test_config_save_rejects_build_dir(tmp_path: Path):
    """Verify that attempting to save config into a build/dist dir redirects to safe default."""
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    unsafe_file = build_dir / "config.json"

    cfg = Config(token="secret_token_123")
    # Calling save with unsafe path should not write to unsafe_file
    with patch("ymusic_cli.config.get_default_config_file") as mock_safe:
        safe_target = tmp_path / "safe_user_dir" / "config.json"
        mock_safe.return_value = safe_target
        cfg.save(unsafe_file)

        assert not unsafe_file.exists(), "Token MUST NOT be saved into build folder!"
        assert safe_target.exists(), "Token should be redirected to safe user directory"


def test_env_token_override():
    """Verify that environment variable YANDEX_MUSIC_TOKEN works."""
    with patch.dict(os.environ, {"YANDEX_MUSIC_TOKEN": "my_env_token_456"}):
        # Fresh config without file
        cfg = Config.load(Path("/nonexistent/path/config.json"))
        assert cfg.token == "my_env_token_456"


def test_clipboard_fallback():
    """Verify copy_to_clipboard executes without unhandled exceptions."""
    res = copy_to_clipboard("test_code")
    assert isinstance(res, bool)


if __name__ == "__main__":
    test_unsafe_paths()
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_config_save_rejects_build_dir(Path(td))
    test_env_token_override()
    test_clipboard_fallback()
    print("ALL CONFIG & TOKEN SECURITY TESTS PASSED SUCCESSFULLY!")
