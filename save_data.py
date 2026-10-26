"""Versioned, atomic persistence for configuration, saves, history, and records."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict

VERSION = 3


def default_config_path() -> Path:
    root = os.environ.get("APPDATA") if os.name == "nt" else os.environ.get("XDG_CONFIG_HOME")
    return Path(root or (Path.home() / ".config")) / "mazequest" / "state.json"


def empty_state() -> Dict[str, Any]:
    return {"version": VERSION, "settings": {"sound": True, "show_hints": True, "fullscreen": False,
                            "scaling": "integer", "volume": 0.7, "fog": False},
            "current": None, "history": [], "personal_bests": {}}


def save_state(path: str | Path, state: Dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(empty_state())
    payload.update(state)
    payload["version"] = VERSION
    temporary = destination.with_name(destination.name + ".writing")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, destination)


def load_state(path: str | Path) -> Dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("version") not in (2, VERSION):
            return empty_state()
        state = empty_state()
        state.update({key: payload[key] for key in state if key in payload})
        if isinstance(payload.get("settings"), dict):
            state["settings"].update(payload["settings"])
        if not isinstance(state.get("current"), dict): state["current"] = None
        if not isinstance(state.get("history"), list): state["history"] = []
        if not isinstance(state.get("personal_bests"), dict): state["personal_bests"] = {}
        return state
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        return empty_state()


# Compatibility helpers for earlier callers.
def save_progress(path: str | Path, data: Dict[str, Any]) -> None:
    save_state(path, {"current": data})


def load_progress(path: str | Path) -> Dict[str, Any]:
    return load_state(path).get("current") or {}
