from __future__ import annotations

import json
import os
from pathlib import Path

from .models import AppConfiguration


APP_FOLDER_NAME = "WL Fechamento"
CONFIG_FILE_NAME = "config.json"


def configuration_directory() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / APP_FOLDER_NAME
    return Path.home() / ".wl_fechamento"


def configuration_path() -> Path:
    return configuration_directory() / CONFIG_FILE_NAME


def load_configuration(path: Path | None = None) -> AppConfiguration:
    target = path or configuration_path()
    if not target.exists():
        return AppConfiguration()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return AppConfiguration.from_dict(data)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppConfiguration()


def save_configuration(config: AppConfiguration, path: Path | None = None) -> Path:
    target = path or configuration_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(config.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)
    return target
