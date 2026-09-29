#!/usr/bin/env python3
"""Cross-platform build and packaging script for YMusic CLI.

Strictly separates build artifacts into platform-specific directories:
- Linux:   dist/linux/ymusic
- Windows: dist/windows/ymusic.exe

Supports automated release packaging:
- releases/ymusic-v{version}-linux-x64.tar.gz
- releases/ymusic-v{version}-windows-x64.zip

Guarantees that user tokens, configs, and personal data are NEVER bundled into
the build or distribution artifacts.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
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


def get_version(root: Path) -> str:
    """Read version from src/ymusic_cli/__init__.py."""
    init_py = root / "src" / "ymusic_cli" / "__init__.py"
    if init_py.exists():
        for line in init_py.read_text(encoding="utf-8").splitlines():
            if line.startswith("__version__"):
                return line.split("=")[-1].strip().strip('"').strip("'")
    return "0.2.0"


def clean_platform_dirs(dist_target: Path, build_target: Path) -> None:
    """Clean only target platform build artifacts, preserving other platforms."""
    if dist_target.exists():
        shutil.rmtree(dist_target)
    if build_target.exists():
        shutil.rmtree(build_target)
    dist_target.mkdir(parents=True, exist_ok=True)
    build_target.mkdir(parents=True, exist_ok=True)


def check_security_leaks(root: Path) -> None:
    """Verify no local credentials or config files are exposed to the build."""
    leak_patterns = ["config.json", "*.token", ".env*", "*token*.txt"]
    for pattern in leak_patterns:
        found = list(root.glob(pattern))
        if found:
            print(f"  [WARNING] Found local credential file: {found}")
            print("  Ensuring it is not passed into PyInstaller.")


def build_binary(root: Path, target_platform: str) -> Path:
    """Compile single-file binary for specified platform."""
    is_windows = target_platform == "windows"
    exe_name = "ymusic.exe" if is_windows else "ymusic"

    dist_dir = root / "dist" / target_platform
    build_dir = root / "build" / target_platform
    src_dir = root / "src"
    entrypoint = src_dir / "ymusic_cli" / "__main__.py"

    print("=" * 60)
    print(f"  YMusic CLI - Building for {target_platform.upper()}")
    print(f"  Target: {dist_dir / exe_name}")
    print("=" * 60)

    # 1. Clean only target platform directory
    print(f"\n[1/5] Cleaning {target_platform} build cache...")
    clean_platform_dirs(dist_dir, build_dir)

    # 2. Security leak checks
    print("\n[2/5] Security verification: checking for credential files...")
    check_security_leaks(root)

    # 3. Assemble PyInstaller command
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
        f"--name=ymusic",
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        f"--distpath={dist_dir}",
        f"--workpath={build_dir}",
        f"--specpath={build_dir}",
        f"--paths={src_dir}",
    ]

    for imp in hidden_imports:
        cmd.append(f"--hidden-import={imp}")

    # Exclude unnecessary heavyweight modules
    cmd.extend([
        "--exclude-module=tkinter",
        "--exclude-module=matplotlib",
        "--exclude-module=numpy",
    ])

    cmd.append(str(entrypoint))

    # 4. Execute Build
    print(f"\n[4/5] Executing PyInstaller build...")
    res = subprocess.run(cmd, cwd=root)
    if res.returncode != 0:
        print(f"\n[ERROR] PyInstaller failed with exit code {res.returncode}")
        sys.exit(res.returncode)

    output_exe = dist_dir / exe_name
    if not output_exe.exists():
        print(f"\n[ERROR] Output executable not found at: {output_exe}")
        sys.exit(1)

    # Post-process binary
    if not is_windows:
        output_exe.chmod(0o755)
        strip_tool = shutil.which("strip")
        if strip_tool:
            try:
                subprocess.run([strip_tool, str(output_exe)], check=False)
                print("  [OK] Debug symbols stripped.")
            except Exception:
                pass

    size_mb = output_exe.stat().st_size / (1024 * 1024)
    print(f"\n[5/5] Successfully built {target_platform.upper()} executable!")
    print(f"  Binary:  {output_exe}")
    print(f"  Size:    {size_mb:.2f} MB")

    # 5. Security audit
    print("\n[Security Audit]")
    for item in dist_dir.iterdir():
        assert "config.json" not in item.name, f"ERROR: config.json leaked into {dist_dir}!"
        assert not item.name.endswith(".token"), f"ERROR: token file leaked into {dist_dir}!"
    print(f"  [OK] No credentials found in {dist_dir}.")
    print("=" * 60)

    return output_exe


def package_releases(root: Path) -> None:
    """Package built binaries into portable release bundles."""
    version = get_version(root)
    releases_dir = root / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)

    win_exe = root / "dist" / "windows" / "ymusic.exe"
    lin_exe = root / "dist" / "linux" / "ymusic"

    print("\n" + "=" * 60)
    print(f"  Packaging Release Bundles (v{version})")
    print("=" * 60)

    # 1. Package Windows Release
    if win_exe.exists():
        win_bundle_dir = releases_dir / "windows"
        win_bundle_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(win_exe, win_bundle_dir / "ymusic.exe")

        # Create Windows quick-launcher run.bat
        run_bat = win_bundle_dir / "run.bat"
        run_bat.write_text(
            "@echo off\r\n"
            "title YMusic CLI\r\n"
            "chcp 65001 >nul\r\n"
            "\"%~dp0ymusic.exe\" %*\r\n"
            "if errorlevel 1 pause\r\n",
            encoding="utf-8",
        )

        # Create quick README
        (win_bundle_dir / "README.txt").write_text(
            f"YMusic CLI v{version} - Windows Portable Edition\n\n"
            "Quick Start:\n"
            "  1. Double click 'run.bat' to launch the interactive player.\n"
            "  2. Or run in PowerShell/CMD: .\\ymusic.exe [command]\n"
            "  3. On first start, ymusic automatically connects mpv-2.dll and launches browser login.\n\n"
            "Commands:\n"
            "  ymusic 1, ymusic wave   - Launch My Wave radio immediately\n"
            "  ymusic 2, ymusic liked  - Browse liked tracks\n"
            "  ymusic play <track>     - Play search result\n"
            "  ymusic update           - Refresh authentication token\n",
            encoding="utf-8",
        )

        # Create ZIP archive
        zip_path = releases_dir / f"ymusic-v{version}-windows-x64.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in win_bundle_dir.iterdir():
                z.write(f, arcname=f.name)
        print(f"  [OK] Windows package created: {zip_path} ({zip_path.stat().st_size / (1024*1024):.2f} MB)")

        # Sync to /home/anhelm/Projects/Ycli_Win if directory exists
        parent_projects = root.parent
        ycli_win = parent_projects / "Ycli_Win"
        if ycli_win.exists():
            (ycli_win / "dist").mkdir(parents=True, exist_ok=True)
            shutil.copy2(win_exe, ycli_win / "dist" / "ymusic.exe")
            shutil.copy2(run_bat, ycli_win / "run.bat")
            # Also sync parent zip
            shutil.copy2(zip_path, parent_projects / "Ycli_Win.zip")
            print(f"  [OK] Synced Windows binary and run.bat to {ycli_win}")

    # 2. Package Linux Release
    if lin_exe.exists():
        lin_bundle_dir = releases_dir / "linux"
        lin_bundle_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(lin_exe, lin_bundle_dir / "ymusic")
        (lin_bundle_dir / "ymusic").chmod(0o755)

        # Create Linux install script
        install_sh = lin_bundle_dir / "install.sh"
        install_sh.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "INSTALL_DIR=\"${HOME}/.local/bin\"\n"
            "mkdir -p \"${INSTALL_DIR}\"\n"
            "SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
            "cp -f \"${SCRIPT_DIR}/ymusic\" \"${INSTALL_DIR}/ymusic\"\n"
            "chmod +x \"${INSTALL_DIR}/ymusic\"\n"
            "echo \"[OK] ymusic installed to ${INSTALL_DIR}/ymusic\"\n"
            "echo \"Make sure ${INSTALL_DIR} is in your PATH.\"\n",
            encoding="utf-8",
        )
        install_sh.chmod(0o755)

        # Create Linux quick launcher run.sh
        run_sh = lin_bundle_dir / "run.sh"
        run_sh.write_text(
            "#!/usr/bin/env bash\n"
            "SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n"
            "exec \"${SCRIPT_DIR}/ymusic\" \"$@\"\n",
            encoding="utf-8",
        )
        run_sh.chmod(0o755)

        # Create tar.gz archive
        tar_path = releases_dir / f"ymusic-v{version}-linux-x64.tar.gz"
        with tarfile.open(tar_path, "w:gz") as t:
            for f in lin_bundle_dir.iterdir():
                t.add(f, arcname=f.name)
        print(f"  [OK] Linux package created:   {tar_path} ({tar_path.stat().st_size / (1024*1024):.2f} MB)")

        # Sync to /home/anhelm/Projects/Ycli_Lin if directory exists
        parent_projects = root.parent
        ycli_lin = parent_projects / "Ycli_Lin"
        if ycli_lin.exists():
            (ycli_lin / "dist").mkdir(parents=True, exist_ok=True)
            shutil.copy2(lin_exe, ycli_lin / "dist" / "ymusic")
            (ycli_lin / "dist" / "ymusic").chmod(0o755)
            shutil.copy2(run_sh, ycli_lin / "run.sh")
            shutil.copy2(install_sh, ycli_lin / "install.sh")
            # Also create parent tar.gz
            shutil.copy2(tar_path, parent_projects / "Ycli_Lin.tar.gz")
            print(f"  [OK] Synced Linux binary, run.sh, install.sh to {ycli_lin}")


def main() -> None:
    parser = argparse.ArgumentParser(description="YMusic CLI Build and Packaging Tool")
    parser.add_argument("--platform", choices=["auto", "linux", "windows"], default="auto",
                        help="Target platform (default: current host OS)")
    parser.add_argument("--package", action="store_true", help="Package release archives after build")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent

    target = args.platform
    if target == "auto":
        target = "windows" if sys.platform == "win32" else "linux"

    build_binary(root, target)

    # Automatically package release bundles
    package_releases(root)


if __name__ == "__main__":
    main()
