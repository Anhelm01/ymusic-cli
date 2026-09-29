"""Automated mpv / libmpv detector and installer for Windows.

Checks for libmpv-2.dll / mpv-2.dll, and if missing, offers one-click automated
download and setup into %LOCALAPPDATA%\\ymusic-cli\\mpv without requiring admin rights.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

log = logging.getLogger(__name__)

# Fallback direct HTTPS URLs for Windows 64-bit mpv developer bundle
FALLBACK_MPV_URLS = [
    "https://github.com/zhongfly/mpv-winbuild/releases/download/2026-09-28-178242c75e/mpv-dev-x86_64-20260928-git-178242c75e.7z",
    "https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/20260928/mpv-dev-x86_64-20260928-git-e470f8986e.7z",
]

DLL_NAMES = ("mpv-2.dll", "libmpv-2.dll", "mpv-1.dll", "libmpv-1.dll")

# Persistent references to os.add_dll_directory cookies to avoid GC de-registration
_DLL_DIRECTORY_COOKIES: list[object] = []


def get_windows_mpv_dir() -> Path:
    """Return dedicated user directory for mpv binaries."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"
    return (base / "ymusic-cli" / "mpv").resolve()


def get_search_directories() -> list[Path]:
    """Return all directories where mpv DLLs might be located."""
    dirs: list[Path] = [
        get_windows_mpv_dir(),
        Path.cwd(),
        Path(sys.executable).parent,
        Path(__file__).resolve().parent.parent.parent,
        Path.home() / "scoop" / "apps" / "mpv" / "current",
        Path.home() / "scoop" / "shims",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "mpv",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "mpv.net",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "mpv",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "mpv.net",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "mpv",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "mpv.net",
    ]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        dirs.insert(0, Path(meipass))

    # Add directories from PATH
    path_env = os.environ.get("PATH", "")
    for p in path_env.split(os.pathsep):
        p_clean = p.strip()
        if p_clean:
            dirs.append(Path(p_clean))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_dirs: list[Path] = []
    for d in dirs:
        try:
            resolved_key = str(d.resolve()).lower()
            if resolved_key not in seen:
                seen.add(resolved_key)
                unique_dirs.append(d)
        except OSError:
            continue

    return unique_dirs


def find_existing_mpv_dll() -> tuple[Path, str] | None:
    """Check if mpv DLL is already present on the system."""
    for folder in get_search_directories():
        try:
            if not folder.is_dir():
                continue
            for dll_name in DLL_NAMES:
                candidate = folder / dll_name
                if candidate.is_file() and candidate.stat().st_size > 1024:
                    return folder, dll_name
        except OSError:
            continue
    return None


def register_mpv_directory(folder: Path) -> None:
    """Register directory in PATH and os.add_dll_directory."""
    folder_str = str(folder.resolve())
    current_path = os.environ.get("PATH", "")
    path_parts = [p.strip() for p in current_path.split(os.pathsep) if p.strip()]

    # Prepend if not already the first entry
    if not path_parts or path_parts[0].lower() != folder_str.lower():
        os.environ["PATH"] = folder_str + os.pathsep + current_path

    # Python 3.8+ Windows DLL directory registration
    if hasattr(os, "add_dll_directory"):
        try:
            cookie = os.add_dll_directory(folder_str)
            _DLL_DIRECTORY_COOKIES.append(cookie)
        except Exception as e:
            log.debug("os.add_dll_directory failed for %s: %s", folder_str, e)

    # Windows kernel32 SetDllDirectoryW fallback
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetDllDirectoryW(folder_str)
        except Exception as e:
            log.debug("SetDllDirectoryW failed for %s: %s", folder_str, e)


def discover_latest_mpv_url() -> str | None:
    """Dynamically discover latest release download URL without API token."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) YMusic-CLI/1.0"}
    try:
        # Step 1: Follow redirect to get latest release tag
        req = urllib.request.Request("https://github.com/zhongfly/mpv-winbuild/releases/latest", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            final_url = resp.geturl()
            tag = final_url.split("/")[-1]

        if tag:
            # Step 2: Fetch expanded assets HTML for this tag
            assets_url = f"https://github.com/zhongfly/mpv-winbuild/releases/expanded_assets/{tag}"
            req_assets = urllib.request.Request(assets_url, headers=headers)
            with urllib.request.urlopen(req_assets, timeout=10) as resp_assets:
                html = resp_assets.read().decode("utf-8", errors="ignore")
                matches = re.findall(r'href="(/zhongfly/mpv-winbuild/releases/download/[^/]+/mpv-dev-x86_64-[^"]+)"', html)
                if matches:
                    # Pick the non-v3 standard x86_64 asset for maximum CPU compatibility
                    standard = [m for m in matches if "-v3-" not in m]
                    choice = standard[0] if standard else matches[0]
                    return f"https://github.com{choice}"
    except Exception as e:
        log.debug("Dynamic discovery failed: %s", e)

    return None


def extract_archive(archive_path: Path, target_dir: Path) -> bool:
    """Extract archive (supports .7z, .zip, etc.) using available extractors."""
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Try zipfile if it is a standard zip archive
    if zipfile.is_zipfile(archive_path):
        try:
            with zipfile.ZipFile(archive_path, "r") as z:
                z.extractall(target_dir)
            return True
        except Exception as e:
            log.warning("zipfile extraction failed: %s", e)

    # 2. Try Windows built-in tar.exe (bsdtar with native 7z and zip support on Win 10 1803+)
    tar_exe = shutil.which("tar")
    if not tar_exe and sys.platform == "win32":
        sys32_tar = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tar.exe"
        if sys32_tar.exists():
            tar_exe = str(sys32_tar)

    if tar_exe:
        try:
            res = subprocess.run(
                [tar_exe, "-xf", str(archive_path), "-C", str(target_dir)],
                capture_output=True,
                timeout=90,
            )
            if res.returncode == 0:
                return True
        except Exception as e:
            log.warning("tar extraction failed: %s", e)

    # 3. Try 7-Zip CLI if installed
    seven_z = shutil.which("7z") or shutil.which("7za")
    if not seven_z and sys.platform == "win32":
        for candidate in [
            Path(r"C:\Program Files\7-Zip\7z.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
        ]:
            if candidate.exists():
                seven_z = str(candidate)
                break

    if seven_z:
        try:
            res = subprocess.run(
                [seven_z, "x", str(archive_path), f"-o{target_dir}", "-y"],
                capture_output=True,
                timeout=90,
            )
            if res.returncode == 0:
                return True
        except Exception as e:
            log.warning("7z CLI extraction failed: %s", e)

    # 4. Try PowerShell Expand-Archive (fallback for zip)
    ps_exe = shutil.which("powershell") or shutil.which("pwsh")
    if ps_exe:
        try:
            cmd = f'Expand-Archive -Path "{archive_path}" -DestinationPath "{target_dir}" -Force'
            res = subprocess.run([ps_exe, "-NoProfile", "-Command", cmd], capture_output=True, timeout=90)
            if res.returncode == 0:
                return True
        except Exception as e:
            log.warning("PowerShell Expand-Archive failed: %s", e)

    return False


def normalize_extracted_dlls(target_dir: Path) -> bool:
    """Flatten extracted DLLs into target_dir and create dual mpv-2 / libmpv-2 aliases."""
    try:
        # Move any DLL found in subdirectories to target_dir root
        for dll_file in list(target_dir.rglob("*.dll")):
            if dll_file.parent != target_dir:
                dest = target_dir / dll_file.name
                shutil.move(str(dll_file), str(dest))

        # Ensure both mpv-2.dll and libmpv-2.dll exist for maximum compatibility
        libmpv = target_dir / "libmpv-2.dll"
        mpv2 = target_dir / "mpv-2.dll"

        if libmpv.exists() and not mpv2.exists():
            shutil.copy2(str(libmpv), str(mpv2))
        elif mpv2.exists() and not libmpv.exists():
            shutil.copy2(str(mpv2), str(libmpv))

        # Check if at least one valid DLL is in target_dir
        for name in DLL_NAMES:
            candidate = target_dir / name
            if candidate.is_file() and candidate.stat().st_size > 1024:
                return True
    except Exception as e:
        log.warning("Normalization of DLLs failed: %s", e)

    return False


def download_and_extract_mpv(target_dir: Path, console: Console | None = None) -> bool:
    """Download mpv DLL package and extract into target_dir."""
    target_dir.mkdir(parents=True, exist_ok=True)
    temp_archive = target_dir / "mpv_download.archive"

    # Assemble candidate URLs (dynamic latest first, then robust fallbacks)
    urls: list[str] = []
    dynamic_url = discover_latest_mpv_url()
    if dynamic_url:
        urls.append(dynamic_url)
    urls.extend(FALLBACK_MPV_URLS)

    download_success = False

    for url in urls:
        try:
            if console:
                console.print(f"[cyan]Загрузка библиотеки mpv ({url.split('/')[-1]})...[/cyan]")

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) YMusic-CLI/1.0"},
            )
            with urllib.request.urlopen(req, timeout=45) as resp, open(temp_archive, "wb") as f_out:
                shutil.copyfileobj(resp, f_out)

            if temp_archive.exists() and temp_archive.stat().st_size > 1024 * 1024:
                download_success = True
                break
        except Exception as e:
            log.warning("Download failed from %s: %s", url, e)
            if temp_archive.exists():
                temp_archive.unlink(missing_ok=True)

    if not download_success or not temp_archive.exists():
        return False

    # Extract archive
    try:
        if console:
            console.print("[cyan]Распаковка аудио-библиотеки mpv...[/cyan]")

        extracted = extract_archive(temp_archive, target_dir)
        temp_archive.unlink(missing_ok=True)

        if not extracted:
            return False

        return normalize_extracted_dlls(target_dir)
    except Exception as e:
        log.error("Failed to extract mpv archive: %s", e)
        if temp_archive.exists():
            temp_archive.unlink(missing_ok=True)
        return False


def reload_mpv_module() -> bool:
    """Reload or import mpv module in Python runtime after registering DLLs."""
    import importlib
    try:
        if "mpv" in sys.modules:
            importlib.reload(sys.modules["mpv"])
        else:
            import mpv  # noqa: F401
        return True
    except Exception as e:
        log.debug("Failed to reload mpv module: %s", e)
        return False


def ensure_mpv_windows(console: Console | None = None, auto_download: bool = True) -> bool:
    """Ensure mpv is available on Windows.

    If missing, prompts to download automatically, registers DLL path, and reloads mpv module.
    """
    if sys.platform != "win32":
        return True

    existing = find_existing_mpv_dll()
    if existing:
        folder, dll_name = existing
        register_mpv_directory(folder)
        reload_mpv_module()
        log.info("Found existing mpv DLL: %s in %s", dll_name, folder)
        return True

    # Check if mpv executable is available in PATH
    if shutil.which("mpv") is not None:
        return True

    if console:
        console.print("\n[yellow][!] Аудио-движок mpv не найден в системе.[/yellow]")
        console.print("Для воспроизведения звука в Windows требуется библиотека [bold]mpv-2.dll[/bold].")

    target_dir = get_windows_mpv_dir()

    should_download = auto_download
    if not auto_download and console:
        try:
            choice = input("Скачать и установить mpv автоматически в профиль пользователя? [Y/n]: ").strip().lower()
            should_download = choice in ("", "y", "yes", "д", "да")
        except (EOFError, KeyboardInterrupt):
            should_download = False

    if not should_download:
        if console:
            console.print("[red][ERROR] mpv не установлен. Воспроизведение звука будет недоступно.[/red]")
            console.print("Установите mpv через winget: [bold]winget install mpv.net[/bold] или scoop.")
        return False

    if console:
        console.print(f"[bold green]Автоматическая установка mpv в {target_dir}...[/bold green]")

    success = download_and_extract_mpv(target_dir, console=console)
    if success:
        existing = find_existing_mpv_dll()
        if existing:
            register_mpv_directory(existing[0])
            reload_mpv_module()
            if console:
                console.print(f"[green][OK] mpv успешно установлен и подключен ({existing[1]})![/green]\n")
            return True

    # If direct download failed, try winget if available
    winget = shutil.which("winget")
    if winget:
        if console:
            console.print("[cyan]Пробую установку через Windows Package Manager (winget)...[/cyan]")
        try:
            res = subprocess.run(
                ["winget", "install", "--id", "mpv.net", "-e", "--accept-source-agreements", "--accept-package-agreements"],
                timeout=120,
            )
            if res.returncode == 0:
                existing = find_existing_mpv_dll()
                if existing:
                    register_mpv_directory(existing[0])
                    reload_mpv_module()
                    if console:
                        console.print("[green][OK] mpv успешно установлен через winget![/green]\n")
                    return True
        except Exception as e:
            log.debug("Winget fallback failed: %s", e)

    if console:
        console.print("[red][ОШИБКА] Не удалось автоматически скачать mpv.[/red]")
        console.print("Пожалуйста, установите mpv вручную командой:")
        console.print("  [bold]winget install mpv.net[/bold]  или  [bold]scoop install mpv[/bold]")
    return False
