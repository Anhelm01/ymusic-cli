"""Tests for Windows mpv auto-download, detection, and normalization logic."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from ymusic_cli.mpv_windows import (
    DLL_NAMES,
    extract_archive,
    find_existing_mpv_dll,
    get_search_directories,
    get_windows_mpv_dir,
    normalize_extracted_dlls,
    register_mpv_directory,
)


def test_get_windows_mpv_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    mpv_dir = get_windows_mpv_dir()
    assert str(tmp_path) in str(mpv_dir)
    assert mpv_dir.name == "mpv"
    assert mpv_dir.parent.name == "ymusic-cli"


def test_get_search_directories_uniqueness(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{tmp_path}")
    dirs = get_search_directories()
    # Check that search directories are unique
    seen = set()
    for d in dirs:
        resolved = str(d.resolve()).lower()
        assert resolved not in seen, f"Duplicate directory found: {resolved}"
        seen.add(resolved)


def test_find_existing_mpv_dll(monkeypatch, tmp_path: Path):
    mock_dir = tmp_path / "custom_mpv"
    mock_dir.mkdir(parents=True)
    fake_dll = mock_dir / "libmpv-2.dll"
    fake_dll.write_bytes(b"\x00" * 2048)  # > 1024 bytes

    with patch("ymusic_cli.mpv_windows.get_search_directories", return_value=[mock_dir]):
        result = find_existing_mpv_dll()
        assert result is not None
        folder, dll_name = result
        assert folder == mock_dir
        assert dll_name == "libmpv-2.dll"


def test_normalize_extracted_dlls_flattens_and_aliases(tmp_path: Path):
    subfolder = tmp_path / "sub" / "bin"
    subfolder.mkdir(parents=True)
    nested_dll = subfolder / "libmpv-2.dll"
    nested_dll.write_bytes(b"\x00" * 4096)

    # Run normalization
    success = normalize_extracted_dlls(tmp_path)
    assert success is True

    # Check flattened
    root_libmpv = tmp_path / "libmpv-2.dll"
    assert root_libmpv.is_file()

    # Check alias created
    root_mpv2 = tmp_path / "mpv-2.dll"
    assert root_mpv2.is_file()
    assert root_mpv2.stat().st_size == root_libmpv.stat().st_size


def test_extract_archive_zip(tmp_path: Path):
    zip_path = tmp_path / "bundle.zip"
    extract_dir = tmp_path / "extracted"

    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("libmpv-2.dll", "sample dll content")

    success = extract_archive(zip_path, extract_dir)
    assert success is True
    assert (extract_dir / "libmpv-2.dll").is_file()


def test_register_mpv_directory(monkeypatch, tmp_path: Path):
    folder = tmp_path / "mpv_bin"
    folder.mkdir()
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    register_mpv_directory(folder)
    path_env = os.environ.get("PATH", "")
    assert str(folder.resolve()) in path_env
    # First entry should be folder
    assert path_env.startswith(str(folder.resolve()))
