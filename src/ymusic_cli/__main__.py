"""Entry point for YMusic CLI.

Cross-platform console player for Yandex Music (Windows & Linux compatible).
"""

from __future__ import annotations

import logging
import sys

from ymusic_cli.auth import run_browser_device_auth
from ymusic_cli.config import Config, get_default_cache_dir


def _setup_windows_console() -> None:
    """Enable UTF-8 and ANSI escape sequences in Windows console."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass

    try:
        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr.encoding.lower() != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def print_cli_version() -> None:
    """Print package version."""
    from ymusic_cli import __version__

    print(f"ymusic {__version__}")


def print_cli_help() -> None:
    """Print command-line usage information (strictly emoji-free)."""
    from rich.console import Console

    console = Console(highlight=False)
    console.print("[bold]ymusic[/bold] - Console player for Yandex Music with ASCII visuals & tabs\n")
    console.print("[bold cyan]Usage:[/bold cyan]")
    console.print("  ymusic                     Launch interactive player shell")
    console.print("  ymusic 1, ymusic wave      Launch and start My Wave radio immediately")
    console.print("  ymusic 2, ymusic liked     Launch and browse liked tracks")
    console.print("  ymusic play <query/number> Launch and play track or search query")
    console.print("  ymusic search <query>      Launch and search for tracks")
    console.print("  ymusic vis                 Launch interactive ASCII spectrum visualizer")
    console.print("  ymusic status              Show account info and exit")
    console.print("  ymusic update, ymusic auth Force update token via browser (Device Auth)")
    console.print("  ymusic update <token>      Authenticate with explicit token")
    console.print("  ymusic --version, -v       Show version and exit")
    console.print("  ymusic --help, -h          Show this help message\n")


def main() -> None:
    """Main entry point."""
    _setup_windows_console()

    log_dir = get_default_cache_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(log_dir / "ymusic.log"),
            level=logging.INFO,
            format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        )
    except OSError:
        pass

    from rich.console import Console
    from ymusic_cli.api import YMusicAPI

    console = Console(highlight=False)
    args = sys.argv[1:]

    # Handle --help / -h
    if args and args[0] in ("--help", "-h", "help"):
        print_cli_help()
        return

    # Handle --version / -v
    if args and args[0] in ("--version", "-v", "version"):
        print_cli_version()
        return

    # Handle 'ymusic update', 'ymusic auth', 'ymusic update-token', 'ymusic token'
    if args and args[0] in ("update", "auth", "update-token", "token"):
        cfg = Config.load()
        if len(args) > 1:
            token = args[1].strip()
            api = YMusicAPI(cfg)
            if api.login(token):
                cfg.token = token
                cfg.save()
                console.print(f"[green][OK] Authenticated as: {api.username}[/green]")
            else:
                console.print("[red][ERROR] Token invalid.[/red]")
                sys.exit(1)
            return

        # Launch automated browser authorization ("взял токен и свалил")
        success = run_browser_device_auth(cfg, auto_exit=True)
        sys.exit(0 if success else 1)

    # Handle 'ymusic status'
    if args and args[0] == "status":
        cfg = Config.load()
        api = YMusicAPI(cfg)
        if not api.login():
            console.print("[red][ERROR] Not authenticated. Run: ymusic auth[/red]")
            sys.exit(1)
        plus = "[green]Active [yes][/green]" if api.has_plus else "[red]Inactive [no][/red]"
        console.print(f"User:   [bold]{api.username}[/bold]")
        console.print(f"Plus:   {plus}")
        console.print(f"Volume: {cfg.volume}%")
        return

    # Determine initial command if any
    initial_cmd = None
    if args:
        subcmd = args[0].lower()
        if subcmd in ("1", "2", "3", "4", "5", "6", "wave", "liked", "playlists", "vis", "lyrics"):
            initial_cmd = subcmd
        elif subcmd in ("play", "search") and len(args) > 1:
            initial_cmd = f"{subcmd} {' '.join(args[1:])}"
        elif subcmd == "play":
            initial_cmd = "play"
        else:
            initial_cmd = " ".join(args)

    cfg = Config.load()
    api = YMusicAPI(cfg)

    # If login fails (empty token or expired token), automatically launch browser device auth
    if not api.login():
        console.print("[yellow]Токен Яндекс Музыки недействителен или отсутствует.[/yellow]")
        console.print("Запускаю автоматическое получение токена через браузер...")
        if run_browser_device_auth(cfg, auto_exit=False):
            api.login()
        else:
            console.print("[dim]Вы можете запустить 'ymusic auth' позже.[/dim]")

    # Setup Windows mpv if needed before importing player/shell
    if sys.platform == "win32":
        from ymusic_cli.mpv_windows import ensure_mpv_windows
        if not ensure_mpv_windows(console=console):
            console.print("[red][ERROR] Не удалось инициализировать аудио-движок mpv.[/red]")
            sys.exit(1)

    from ymusic_cli.cli import YMusicShell

    shell = YMusicShell(cfg, api)
    shell.start(initial_command=initial_cmd)


if __name__ == "__main__":
    main()
