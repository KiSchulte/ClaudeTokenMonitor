"""Einstellungen (JSON unter ~/.config) und Autostart (~/.config/autostart).

Bewusst kein GSettings: dafür müsste ein Schema systemweit oder mit
GSETTINGS_SCHEMA_DIR installiert und kompiliert werden.
"""

from __future__ import annotations

import json
import os
import shlex
import sys

from . import APP_ID, APP_NAME
from .loc import LANGUAGE_CHOICES, SYSTEM

METRIC_BLOCK_TOKENS = "blockTokens"
METRIC_TODAY_TOKENS = "todayTokens"
METRIC_TODAY_COST = "todayCost"
METRIC_MONTH_COST = "monthCost"
METRICS = (METRIC_BLOCK_TOKENS, METRIC_TODAY_TOKENS, METRIC_TODAY_COST, METRIC_MONTH_COST)


def _config_home() -> str:
    return os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")


class Settings:
    def __init__(self) -> None:
        self.path = os.path.join(_config_home(), "claude-token-monitor", "settings.json")
        self.language = SYSTEM
        self.metric = METRIC_BLOCK_TOKENS
        self.show_cost = False
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        if data.get("language") in LANGUAGE_CHOICES:
            self.language = data["language"]
        if data.get("metric") in METRICS:
            self.metric = data["metric"]
        self.show_cost = bool(data.get("showCost", False))

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"language": self.language, "metric": self.metric,
                       "showCost": self.show_cost}, f, indent=2)
        os.replace(tmp, self.path)


# MARK: - Autostart


def autostart_path() -> str:
    return os.path.join(_config_home(), "autostart", f"{APP_ID}.desktop")


def autostart_enabled() -> bool:
    return os.path.isfile(autostart_path())


def _launch_command() -> str:
    """Bevorzugt den installierten Starter, sonst den aktuellen Speicherort."""
    launcher = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude-token-monitor")
    if os.access(launcher, os.X_OK):
        return shlex.quote(launcher)
    main = os.path.abspath(sys.argv[0])
    return f"{shlex.quote(sys.executable)} {shlex.quote(main)}"


def set_autostart(enabled: bool) -> str | None:
    """Gibt bei Fehlern eine Meldung zurück."""
    path = autostart_path()
    try:
        if not enabled:
            if os.path.exists(path):
                os.remove(path)
            return None
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                "[Desktop Entry]\n"
                "Type=Application\n"
                f"Name={APP_NAME}\n"
                f"Exec={_launch_command()} --hidden\n"
                f"Icon={APP_ID}\n"
                "X-GNOME-Autostart-enabled=true\n"
                "X-GNOME-Autostart-Delay=5\n"
                "NoDisplay=true\n"
            )
        return None
    except OSError as e:
        return str(e)
