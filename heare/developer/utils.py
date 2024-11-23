import json
import os
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, IO

from prompt_toolkit.completion import Completer, WordCompleter, Completion

# Constants for app name and directories
APP_NAME = "heare"
DEFAULT_CONFIG_DIR = Path.home() / ".config" / APP_NAME
DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME


def get_config_dir() -> Path:
    """Get the configuration directory for the application."""
    config_dir = os.environ.get("XDG_CONFIG_HOME", DEFAULT_CONFIG_DIR)
    return Path(config_dir)


def get_data_dir() -> Path:
    """Get the data directory for the application."""
    data_dir = os.environ.get("XDG_DATA_HOME", DEFAULT_DATA_DIR)
    return Path(data_dir)


def ensure_dir_exists(directory: Path) -> None:
    """Ensure that the given directory exists."""
    directory.mkdir(parents=True, exist_ok=True)


def get_config_file(filename: str) -> Path:
    """Get the path to a configuration file."""
    config_dir = get_config_dir()
    ensure_dir_exists(config_dir)
    return config_dir / filename


def get_data_file(filename: str) -> Path:
    """Get the path to a data file."""
    data_dir = get_data_dir()
    ensure_dir_exists(data_dir)
    return data_dir / filename


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Enum):
            return obj.name
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, SimpleNamespace):
            return vars(obj)
        if hasattr(obj, "__dict__"):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        if hasattr(obj, "__slots__"):
            return {
                slot: getattr(obj, slot) for slot in obj.__slots__ if hasattr(obj, slot)
            }
        return super().default(obj)


def serialize_to_file(obj: Any, fp: IO[str], indent: int = None) -> None:
    json.dump(obj, fp, cls=CustomJSONEncoder, indent=indent)


def load_config(filename: str = "config.json") -> dict:
    """
    Load a configuration file from the config directory
    """
    config_file = get_config_file(filename)
    if config_file.exists():
        with open(config_file, "r") as f:
            return json.load(f)
    return {}


def save_config(config: dict, filename: str = "config.json") -> None:
    """
    Save a configuration file to the config directory
    """
    config_file = get_config_file(filename)
    with open(config_file, "w") as f:
        serialize_to_file(config, f, indent=2)


class CustomCompleter(Completer):
    def __init__(self, commands, history):
        self.commands = commands
        self.history = history
        self.word_completer = WordCompleter(
            list(commands.keys()), ignore_case=True, sentence=True, meta_dict=commands
        )

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if text.startswith("/"):
            yield from self.word_completer.get_completions(document, complete_event)
        else:
            for history_item in reversed(self.history.get_strings()):
                if history_item.startswith(text):
                    yield Completion(history_item, start_position=-len(text))
