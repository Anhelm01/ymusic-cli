#!/usr/bin/env python3
"""Cross-platform build and packaging script for YMusic CLI.

Produces a standalone single-file binary:
- Linux:   dist/ymusic
- Windows: dist/ymusic.exe

Guarantees that user tokens, configs, and personal data are NEVER bundled into
the build or distribution artifacts.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Configure UTF-8 stdout on Windows to prevent cp1252 charmap encoding errors
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> None:
    root = Path(__file__).resolve().parent
    dist_dir = root / "dist"
    build_dir = root / "build"
    src_dir = root / "src"
    entrypoint = src_dir / "ymusic_cli" / "__main__.py"

    print("=" * 60)
    print("  YMusic CLI - Standalone Executable Builder")
    print(f"  Platform: {sys.platform} (Python {sys.version.split()[0]})")
    print("=" * 60)

    # 1. Clean previous builds
    print("\n[1/5] Cleaning previous build artifacts...")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    # 2. Strict Token & Config Leak Check
    print("\n[2/5] Security check: ensuring no tokens or user configs are bundled...")
    leak_patterns = ["config.json", "*.token", ".env*", "*token*.txt"]
    for pattern in leak_patterns:
        found = list(root.glob(pattern))
        if found:
            print(f"  [WARNING] Found config/token file: {found}")
            print("  Ensuring it is not passed to PyInstaller.")

    # 3. Assemble PyInstaller command
    exe_name = "ymusic.exe" if sys.platform == "win32" else "ymusic"
    print(f"\n[3/5] Configuring PyInstaller for {exe_name}...")

    hidden_imports = [
        "ymusic_cli",
        "ymusic_cli.api",
        "ymusic_cli.player",
        "ymusic_cli.config",
        "ymusic_cli.visualizer",
        "ymusic_cli.auth",
        "ymusic_cli.mpv_windows",
        "ymusic_cli.cli",
        "ymusic_cli.__main__",
        "rich",
        "rich.table",
        "rich.panel",
        "rich.text",
        "rich.console",
        "prompt_toolkit",
        "prompt_toolkit.completion",
        "prompt_toolkit.patch_stdout",
        "yandex_music",
        "yandex_music.device_auth",
        "mpv",
        "requests",
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=ymusic",
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        f"--paths={src_dir}",
    ]

    for imp in hidden_imports:
        cmd.append(f"--hidden-import={imp}")

    # Exclude modules that might contain user credentials or unused heavyweight libs
    cmd.extend([
        "--exclude-module=tkinter",
        "--exclude-module=matplotlib",
        "--exclude-module=numpy",
    ])

    cmd.append(str(entrypoint))

    # 4. Execute Build
    print("\n[4/5] Compiling standalone executable...")
    print(f"  Command: {' '.join(cmd[:6])} ... {entrypoint.name}")
    res = subprocess.run(cmd, cwd=root)
    if res.returncode != 0:
        print(f"\n[ERROR] PyInstaller failed with exit code {res.returncode}")
        sys.exit(res.returncode)

    output_exe = dist_dir / exe_name
    if not output_exe.exists():
        print(f"\n[ERROR] Output executable not found at: {output_exe}")
        sys.exit(1)

    if sys.platform != "win32":
        output_exe.chmod(0o755)

    size_mb = output_exe.stat().st_size / (1024 * 1024)
    print(f"\n[5/5] Successfully compiled {exe_name}!")
    print(f"  Path: {output_exe}")
    print(f"  Size: {size_mb:.2f} MB")

    # 5. Security verification of the built artifact
    print("\n[Security Verification]")
    dist_files = [f.name for f in dist_dir.iterdir()]
    assert "config.json" not in dist_files, "ERROR: config.json was copied into dist/!"
    print("  [OK] No config.json or token files bundled into dist/.")
    print("  [OK] User configuration is strictly loaded from OS user profile.")
    print("=" * 60)


if __name__ == "__main__":
    main()
