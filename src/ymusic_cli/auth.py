"""Automated browser-based authentication for YMusic CLI.

Launches the system browser, performs Yandex OAuth Device Authorization,
extracts the token, stores it securely in user config, and completes cleanly.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from typing import TYPE_CHECKING

from rich.console import Console
from yandex_music import Client

if TYPE_CHECKING:
    from ymusic_cli.config import Config


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard across Linux, Windows, and macOS."""
    clean_text = text.strip()
    if sys.platform == "win32":
        try:
            subprocess.run(["clip"], input=clean_text.encode("utf-8"), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False
    elif sys.platform == "darwin":
        try:
            subprocess.run(["pbcopy"], input=clean_text.encode("utf-8"), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False
    else:
        # Linux (Wayland / X11)
        if os.environ.get("WAYLAND_DISPLAY"):
            try:
                subprocess.run(["wl-copy"], input=clean_text.encode("utf-8"), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass
        try:
            subprocess.run(["xclip", "-selection", "clipboard"], input=clean_text.encode("utf-8"), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass
        try:
            subprocess.run(["xsel", "-b", "-i"], input=clean_text.encode("utf-8"), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass
    return False


def run_browser_device_auth(cfg: Config, auto_exit: bool = False) -> bool:
    """Launch browser, perform OAuth Device Auth, save token, and cleanly finish."""
    console = Console(highlight=False)
    console.print("\n[bold cyan]-- Авторизация Yandex Music --[/bold cyan]\n")

    client = Client()
    try:
        code = client.request_device_code()
    except Exception as e:
        console.print(f"[red]Ошибка при запросе кода авторизации:[/red] {e}")
        return False

    user_code = code.user_code
    url = getattr(code, "verification_url", "https://ya.ru/device")

    copied = copy_to_clipboard(user_code)
    clip_hint = " [green](код скопирован в буфер обмена)[/green]" if copied else ""

    console.print(f"1. Код устройства: [bold yellow]{user_code}[/bold yellow]{clip_hint}")
    console.print(f"2. Открываю браузер: [underline cyan]{url}[/underline cyan]")
    console.print("3. Вставьте код и нажмите [bold green]Разрешить[/bold green] в браузере.\n")

    # Launch browser
    try:
        webbrowser.open(url)
    except Exception:
        console.print("[yellow]Не удалось автоматически открыть браузер. Откройте ссылку вручную.[/yellow]")

    console.print("[dim]Ожидание подтверждения в браузере...[/dim]")

    deadline = time.time() + (code.expires_in or 300)
    interval = code.interval or 3

    while time.time() < deadline:
        try:
            token = client.poll_device_token(code.device_code)
            if token and token.access_token:
                # Save token securely into user config
                cfg.token = token.access_token
                cfg.save()
                console.print("\n[bold green][OK] Токен успешно получен и сохранён в конфигурацию![/bold green]")

                # Verify token
                try:
                    test_client = Client(token.access_token).init()
                    username = getattr(test_client.me.account, "full_name", None) or test_client.me.account.login
                    console.print(f"Пользователь: [bold]{username}[/bold]")
                    has_plus = test_client.account_status().plus.has_plus
                    plus_str = "[green]Активен[/green]" if has_plus else "[red]Не активен[/red]"
                    console.print(f"Плюс: {plus_str}\n")
                except Exception:
                    pass

                if auto_exit:
                    sys.exit(0)
                return True
        except Exception:
            pass

        time.sleep(interval)

    console.print("[red]Время ожидания подтверждения истекло.[/red]")
    return False
