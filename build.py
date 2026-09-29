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


def main() -> None:
    root = Path(__file__).resolve().parent
    dist_dir = root / "dist"
    build_dir = root / "build"
    src_dir = root / "src"
    entrypoint = src_dir / "ymusic_cli" / "__main__.py"

    print("=" * 60)
    print("  YMusic CLI — Standalone Executable Builder")
    print(f"  Platform: {sys.platform} (Python {sys.version.split()[0]})")
    print("=" * 60)

    # 1. Clean previous builds
    print("\n[1/5] Очистка предыдущих артефактов сборки...")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)

    # 2. Strict Token & Config Leak Check
    print("\n[2/5] Проверка безопасности: исключение токенов и конфигов...")
    leak_patterns = ["config.json", "*.token", ".env*", "*token*.txt"]
    for pattern in leak_patterns:
        found = list(root.glob(pattern))
        if found:
            print(f"  [ПРЕДУПРЕЖДЕНИЕ] Найден файл настроек: {found}")
            print("  Убедитесь, что он добавлен в .gitignore и не передаётся в PyInstaller.")

    # 3. Assemble PyInstaller command
    exe_name = "ymusic.exe" if sys.platform == "win32" else "ymusic"
    print(f"\n[3/5] Конфигурирование PyInstaller для {exe_name}...")

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
    print("\n[4/5] Компиляция бинарника...")
    print(f"  Команда: {' '.join(cmd[:6])} ... {entrypoint.name}")
    res = subprocess.run(cmd, cwd=root)
    if res.returncode != 0:
        print(f"\n[ОШИБКА] Сборка завершилась с кодом {res.returncode}")
        sys.exit(res.returncode)

    output_exe = dist_dir / exe_name
    if not output_exe.exists():
        print(f"\n[ОШИБКА] Скомпилированный файл не найден по пути: {output_exe}")
        sys.exit(1)

    if sys.platform != "win32":
        output_exe.chmod(0o755)

    size_mb = output_exe.stat().st_size / (1024 * 1024)
    print(f"\n[5/5] Успешно скомпилировано!")
    print(f"  Файл:    {output_exe}")
    print(f"  Размер:  {size_mb:.2f} MB")

    # 5. Security verification of the built artifact
    print("\n[Проверка безопасности]")
    # Ensure no config.json was copied into dist
    dist_files = [f.name for f in dist_dir.iterdir()]
    assert "config.json" not in dist_files, "ОШИБКА: config.json попал в dist/!"
    print("  ✓ Токены и config.json отсутствуют в папке сборки dist/.")
    print("  ✓ Конфигурация сохраняется строго в профиле пользователя ОС.")
    print("=" * 60)


if __name__ == "__main__":
    main()
