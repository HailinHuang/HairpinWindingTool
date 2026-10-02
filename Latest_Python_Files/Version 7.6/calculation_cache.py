"""Versioned, data-only storage for completed winding calculations."""

from __future__ import annotations

from collections import namedtuple
from contextlib import closing
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import zlib

from calculation_state import CalculationState
from get_winding_pattern import _CandidateBranches


SCHEMA_VERSION = 1
_SOURCE_DIGEST = None
_REQUIRED_STATE_VALUES = {
    "num_slots", "copper_fill_factor", "Rphase_active", "W_cond", "H_cond",
    "K_bend_side", "K_bend_height", "EW_info", "Stator_Para",
    "Winding_Para", "Inslot_Para", "Layout_Para", "all_branch_adjustments",
    "Line_Para", "Fig_Para", "TP_info", "base_start_conductor_ids",
    "base_db_conductor_id", "base_cond_info", "db_conductor_id",
    "start_conductor_ids", "phase_A_conductor_id", "cond_info", "results",
    "candidate_report",
}


def _source_digest():
    global _SOURCE_DIGEST
    if _SOURCE_DIGEST is None:
        root = Path(__file__).resolve().parent
        digest = sha256()
        for path in sorted(root.glob("*.py")):
            if path.name.startswith("test_"):
                continue
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        _SOURCE_DIGEST = digest.hexdigest()
    return _SOURCE_DIGEST


def _cache_path():
    override = os.environ.get("HAIRPIN_CALC_CACHE_PATH")
    if override:
        return Path(override)
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache")
    return base / "HairpinWindingScript" / "calculations-v1.sqlite3"


def _encode(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Fraction):
        return {"type": "fraction", "n": value.numerator, "d": value.denominator}
    if isinstance(value, _CandidateBranches):
        return {"type": "branches", "items": _encode(list(value)),
                "attrs": _encode(vars(value))}
    if isinstance(value, tuple) and hasattr(value, "_fields"):
        return {"type": "record", "name": type(value).__name__,
                "fields": list(value._fields), "items": [_encode(item) for item in value]}
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [_encode(item) for item in value]}
    if isinstance(value, list):
        return {"type": "list", "items": [_encode(item) for item in value]}
    if isinstance(value, set):
        return {"type": "set", "items": [_encode(item) for item in value]}
    if isinstance(value, dict):
        return {"type": "dict", "items": [[_encode(key), _encode(item)]
                                          for key, item in value.items()]}
    raise TypeError(f"Calculation cache cannot store {type(value).__name__}")


def _decode(value):
    if not isinstance(value, dict):
        return value
    kind = value["type"]
    if kind == "fraction":
        return Fraction(value["n"], value["d"])
    if kind == "tuple":
        return tuple(_decode(item) for item in value["items"])
    if kind == "list":
        return [_decode(item) for item in value["items"]]
    if kind == "set":
        return {_decode(item) for item in value["items"]}
    if kind == "dict":
        return {_decode(key): _decode(item) for key, item in value["items"]}
    if kind == "record":
        record = namedtuple(value["name"], value["fields"])
        return record(*(_decode(item) for item in value["items"]))
    if kind == "branches":
        branches = _CandidateBranches(_decode(value["items"]))
        branches.__dict__.update(_decode(value["attrs"]))
        return branches
    raise ValueError(f"Unknown calculation cache type: {kind}")


def _key(signature):
    encoded = json.dumps(_encode(tuple(signature)), sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    return sha256((str(SCHEMA_VERSION) + _source_digest() + encoded).encode("utf-8")).hexdigest()


def _open_database(path):
    connection = sqlite3.connect(path, timeout=1)
    connection.execute("CREATE TABLE IF NOT EXISTS calculations "
                       "(cache_key TEXT PRIMARY KEY, payload BLOB NOT NULL)")
    connection.execute("CREATE TABLE IF NOT EXISTS auto_results "
                       "(cache_key TEXT PRIMARY KEY, payload BLOB NOT NULL)")
    return connection


def load_auto(parameters):
    """Read a previously selected Auto layout without running recipe search."""
    path = _cache_path()
    if not path.is_file():
        return None
    try:
        with closing(_open_database(path)) as connection:
            row = connection.execute(
                "SELECT payload FROM auto_results WHERE cache_key = ?",
                (_key(parameters),)).fetchone()
        if row is None:
            return None
        starts, database = _decode(json.loads(zlib.decompress(row[0])))
        if (not isinstance(starts, list)
                or not isinstance(database, _CandidateBranches)
                or not hasattr(database, "layout_report")
                or not hasattr(database, "auto_configuration")):
            return None
        return starts, database
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError, zlib.error):
        return None


def save_auto(parameters, starts, database):
    """Persist the selected Auto result independently of plot settings."""
    try:
        data = zlib.compress(json.dumps(_encode((starts, database)),
                                        separators=(",", ":"), allow_nan=False).encode("utf-8"))
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(_open_database(path)) as connection, connection:
            connection.execute("INSERT OR REPLACE INTO auto_results VALUES (?, ?)",
                               (_key(parameters), data))
        return True
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return False


def load(signature):
    """Return a matching state, or None for a missing or damaged cache."""
    path = _cache_path()
    if not path.is_file():
        return None
    try:
        with closing(_open_database(path)) as connection:
            row = connection.execute(
                "SELECT payload FROM calculations WHERE cache_key = ?", (_key(signature),)
            ).fetchone()
        if row is None:
            return None
        stored = json.loads(zlib.decompress(row[0]))
        if stored["schema"] != SCHEMA_VERSION:
            return None
        restored_signature = _decode(stored["signature"])
        if restored_signature != tuple(signature):
            return None
        values = _decode(stored["values"])
        if not isinstance(values, dict) or not _REQUIRED_STATE_VALUES <= values.keys():
            return None
        return CalculationState.create(restored_signature, stored["generation"], **values)
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError, zlib.error):
        return None


def save(state):
    """Save one completed state; a storage failure cannot invalidate a result."""
    try:
        payload = {"schema": SCHEMA_VERSION, "signature": _encode(state.signature),
                   "generation": state.generation, "values": _encode(dict(state.values))}
        data = zlib.compress(json.dumps(payload, separators=(",", ":"),
                                        allow_nan=False).encode("utf-8"))
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(_open_database(path)) as connection, connection:
            connection.execute("INSERT OR REPLACE INTO calculations VALUES (?, ?)",
                               (_key(state.signature), data))
        return True
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return False
