"""Versioned, atomic persistence for configuration, saves, history, and records."""
# =============================================================================
# WHAT THIS FILE IS
# -----------------------------------------------------------------------------
# Everything that has to survive closing the game is kept in ONE JSON file:
#   settings        - sound, volume, fullscreen, scaling, hints, fog of war
#   current         - the game in progress (so "Continue" works), or None
#   history         - a list of every finished run
#   personal_bests  - the best time / fewest moves
# JSON is a plain-text format of nested dictionaries and lists that Python can
# read and write easily.
#
# Two safety ideas are used here:
#   * VERSIONING - the file stores a version number, so a file written by an
#     incompatible older/newer game is ignored instead of crashing the game.
#   * ATOMIC WRITES - data is written to a temporary file first and then swapped
#     into place in one step, so a crash mid-save can never leave a half-written,
#     corrupted save file.
# =============================================================================

# Lets type hints refer to names defined later in the file.
from __future__ import annotations

# json converts Python dictionaries/lists to and from text; os talks to the
# operating system (environment variables, atomic file replace).
import json
import os

# Path is a convenient object for file and folder locations (works on Windows and others).
from pathlib import Path

# Only used to describe types to readers/editors; no effect when the game runs.
from typing import Any, Dict

# The current save-file format number. Bump it when the layout changes in a way
# that older code could not understand.
VERSION = 3


def default_config_path() -> Path:
    """Where the save file lives on this computer."""
    # On Windows ("nt") use the APPDATA folder; on other systems use XDG_CONFIG_HOME.
    root = os.environ.get("APPDATA") if os.name == "nt" else os.environ.get("XDG_CONFIG_HOME")
    # If that variable is not set, fall back to ~/.config. Then add the game's own
    # folder and file name. The `/` operator joins path pieces.
    return Path(root or (Path.home() / ".config")) / "mazequest" / "state.json"


def empty_state() -> Dict[str, Any]:
    """A brand-new save: default settings, no game in progress, no history."""
    return {"version": VERSION,
            # Default settings used when the player has not changed anything.
            "settings": {"sound": True, "show_hints": True, "fullscreen": False,
                         "scaling": "integer", "volume": 0.7, "fog": False},
            # None means "no game in progress to continue".
            "current": None, "history": [], "personal_bests": {}}


def save_state(path: str | Path, state: Dict[str, Any]) -> None:
    """Write `state` to disk safely (atomic replace)."""
    destination = Path(path)
    # Make sure the folder exists (parents=True creates missing parent folders too;
    # exist_ok=True means "no error if it is already there").
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Start from a complete default state, then lay the given values on top, so the
    # saved file always has every expected key even if `state` is missing some.
    payload = dict(empty_state())
    payload.update(state)
    # Always stamp the current format version.
    payload["version"] = VERSION
    # Write to a sibling file first (state.json.writing)...
    temporary = destination.with_name(destination.name + ".writing")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # ...then swap it over the real file in a single operation. If the program
    # crashes before this line, the old save is untouched.
    os.replace(temporary, destination)


def load_state(path: str | Path) -> Dict[str, Any]:
    """Read the save file; on ANY problem quietly fall back to a fresh default state."""
    try:
        # Read the text and parse it into Python dictionaries/lists.
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        # Only versions 2 and 3 are understood; anything else is ignored.
        if payload.get("version") not in (2, VERSION):
            return empty_state()
        # Begin with the defaults, then copy over each top-level key found in the file.
        state = empty_state()
        state.update({key: payload[key] for key in state if key in payload})
        # Merge saved settings INTO the defaults so a setting added in a newer game
        # version (missing from an old file) keeps its default value.
        if isinstance(payload.get("settings"), dict):
            state["settings"].update(payload["settings"])
        # Defend against a damaged/edited file: each part must have the right type,
        # otherwise reset just that part.
        if not isinstance(state.get("current"), dict):
            state["current"] = None
        if not isinstance(state.get("history"), list):
            state["history"] = []
        if not isinstance(state.get("personal_bests"), dict):
            state["personal_bests"] = {}
        return state
    # File missing/unreadable (OSError), not valid JSON, or wrong shape: start fresh.
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        return empty_state()


# Compatibility helpers for earlier callers.
def save_progress(path: str | Path, data: Dict[str, Any]) -> None:
    """Save only the game-in-progress (older name kept so old code still works)."""
    save_state(path, {"current": data})


def load_progress(path: str | Path) -> Dict[str, Any]:
    """Load only the game-in-progress; returns {} if there is none."""
    return load_state(path).get("current") or {}
