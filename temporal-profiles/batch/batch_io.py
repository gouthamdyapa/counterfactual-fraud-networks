#!/usr/bin/env python3
"""Locate a previous local pilot's input without reading transaction contents.

Python 3.8+ standard library. Discovery reads only a bounded number of saved
pilot metadata files. The batch runner must still verify the complete CSV and
cache before use; metadata discovery is not source validation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
from typing import Any, Dict, Iterable, List, Optional, Tuple


HERE = Path(__file__).resolve().parent
PILOT_PREFIX = "temporal_profile_mac_pilot"
SOURCE_SHA256 = "b19d39f515523373f991b689c07e11e7b0b95c17a2c27a87d91584ae16c5b040"
CACHE_FILENAME = "ibm_raw_v1_%s.sqlite3" % SOURCE_SHA256
MAX_SEARCH_ROOTS = 8
MAX_DIRECTORY_ENTRIES = 4096
MAX_PILOT_DIRECTORIES = 24
MAX_RECORDS_PER_PILOT = 32
MAX_DISCOVERY_RECORDS = 128
MAX_RECORD_BYTES = 4 * 1024 * 1024


def _resolved(path: Any) -> Path:
    try:
        return Path(path).expanduser().resolve()
    except (TypeError, ValueError, OSError, RuntimeError) as exc:
        raise ValueError("Could not read the selected local path: %s" % exc) from exc


def parse_drag_path(text: Any) -> Optional[Path]:
    """Parse one literal, quoted, or Finder-escaped path; never execute text."""
    if not isinstance(text, str):
        raise ValueError("The dragged path must be text")
    text = text.strip()
    if not text:
        return None
    try:
        direct = Path(text).expanduser()
        if direct.exists():
            return direct.resolve()
    except (ValueError, OSError, RuntimeError):
        pass
    try:
        parts = shlex.split(text, posix=True)
    except ValueError as exc:
        raise ValueError("Could not read the dragged path: %s" % exc) from exc
    if len(parts) != 1:
        raise ValueError("Drag one pilot folder or one CSV file at a time")
    return _resolved(parts[0])


def _directory_entries(path: Path) -> Iterable[os.DirEntry]:
    """Inspect immediate children only; never recurse through the home folder."""
    try:
        with os.scandir(str(path)) as entries:
            for index, entry in enumerate(entries):
                if index >= MAX_DIRECTORY_ENTRIES:
                    break
                yield entry
    except OSError:
        return


def _mtime(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _pilot_directories(search_roots: Any) -> List[Path]:
    if search_roots is None:
        roots = [HERE.parent, Path.home() / "Downloads"]
    elif isinstance(search_roots, (str, os.PathLike)):
        roots = [search_roots]
    else:
        try:
            roots = list(search_roots)
        except TypeError as exc:
            raise ValueError("search_roots must be a local path or an iterable of paths") from exc
    found = set()
    inspected = set()
    for raw_root in roots[:MAX_SEARCH_ROOTS]:
        try:
            root = _resolved(raw_root)
        except ValueError:
            continue
        try:
            if root in inspected or not root.is_dir():
                continue
        except OSError:
            continue
        inspected.add(root)
        if root.name.startswith(PILOT_PREFIX):
            found.add(root)
        for entry in _directory_entries(root):
            if not entry.name.startswith(PILOT_PREFIX):
                continue
            try:
                if entry.is_dir(follow_symlinks=True):
                    found.add(_resolved(entry.path))
            except (OSError, ValueError):
                continue
    return sorted(found, key=lambda p: (_mtime(p), str(p)), reverse=True)[:MAX_PILOT_DIRECTORIES]


def _record_candidates(pilot_dir: Path) -> List[Tuple[str, int, Path, Path]]:
    candidates = []
    for entry in _directory_entries(pilot_dir / "runs"):
        if not entry.name.startswith("run_"):
            continue
        try:
            if not entry.is_dir(follow_symlinks=True):
                continue
            record = Path(entry.path) / "run_details.json"
            if record.is_file():
                candidates.append((entry.name, _mtime(record), record, pilot_dir))
        except OSError:
            continue
    # Saved pilot run names begin with UTC timestamps, so lexical order retains
    # run chronology even when a folder copy changed filesystem modification times.
    candidates.sort(key=lambda item: (item[0], item[1], str(item[2])), reverse=True)
    return candidates[:MAX_RECORDS_PER_PILOT]


def _read_record(path: Path) -> Dict[str, Any]:
    try:
        if not path.is_file() or path.stat().st_size > MAX_RECORD_BYTES:
            raise ValueError("The selected pilot record is absent or too large for metadata discovery")
        with path.open("rb") as stream:
            raw = stream.read(MAX_RECORD_BYTES + 1)
        if len(raw) > MAX_RECORD_BYTES:
            raise ValueError("The selected pilot record grew beyond the metadata read limit")
        record = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Could not read the saved pilot metadata: %s" % exc) from exc
    if not isinstance(record, dict):
        raise ValueError("The saved pilot metadata must be an object")
    return record


def _absolute_saved_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("The saved pilot has no usable %s" % label)
    try:
        candidate = Path(value).expanduser()
    except (ValueError, RuntimeError) as exc:
        raise ValueError("The saved pilot has an invalid %s" % label) from exc
    if not candidate.is_absolute():
        raise ValueError("The saved pilot's %s must be an absolute local path" % label)
    return _resolved(candidate)


def _input_from_record(record_path: Path, pilot_dir: Path) -> Dict[str, Any]:
    record = _read_record(record_path)
    summary = record.get("summary")
    cache = record.get("cache")
    if not isinstance(summary, dict) or not isinstance(cache, dict):
        raise ValueError("The selected record has no completed source/cache metadata")
    if (summary.get("application") != "temporal_profile_mac_pilot"
            or summary.get("run_kind") != "data_pilot"):
        raise ValueError("Select an IBM data-pilot record, rather than the synthetic demo record")
    source = summary.get("source")
    if not isinstance(source, dict):
        raise ValueError("The selected record has no verified source identity")
    if source.get("sha256") != SOURCE_SHA256 or cache.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("The saved source/cache identity does not match the original IBM CSV")
    run_id = summary.get("run_id")
    if not isinstance(run_id, str) or not run_id.startswith("run_") or any(c.isspace() for c in run_id):
        raise ValueError("The saved pilot record has no usable run ID")
    csv_path = _absolute_saved_path(record.get("source_path"), "source path")
    if not csv_path.is_file():
        raise ValueError("The CSV recorded by this pilot is no longer at its saved path; drag the original CSV file instead")
    database = _absolute_saved_path(cache.get("database"), "cache path")
    pilot_dir = _resolved(pilot_dir)
    # Reuse an existing custom cache if that is what the selected prior run used.
    # If a pilot folder was moved, prefer its current cache location instead of
    # recreating an obsolete absolute folder from the old saved metadata.
    if database.name == CACHE_FILENAME and database.is_file():
        cache_dir = database.parent
    else:
        cache_dir = (pilot_dir / "cache").resolve()
    return {"pilot_dir": pilot_dir, "csv_path": csv_path,
            "cache_dir": cache_dir, "run_id": run_id}


def discover_prior_inputs(search_roots: Any = None) -> List[Dict[str, Any]]:
    """Return newest compatible saved inputs from a bounded local search.

    Only immediate pilot directories and their saved run metadata are examined.
    Neither the CSV contents nor the SQLite database is opened by discovery.
    Missing, stale, demo, mismatched, oversized, and malformed records are skipped.
    The caller must still verify source bytes/cache completion before execution.
    """
    candidates = []
    for directory in _pilot_directories(search_roots):
        candidates.extend(_record_candidates(directory))
    candidates.sort(key=lambda item: (item[0], item[1], str(item[2])), reverse=True)
    inputs = []
    seen = set()
    for _name, _mtime_ns, record_path, pilot_dir in candidates[:MAX_DISCOVERY_RECORDS]:
        try:
            item = _input_from_record(record_path, pilot_dir)
        except (ValueError, OSError, RuntimeError):
            continue
        key = (str(item["csv_path"]), str(item["cache_dir"]))
        if key not in seen:
            seen.add(key)
            inputs.append(item)
    return inputs


def _explicit_record_input(record: Path) -> Dict[str, Any]:
    run_dir = record.parent
    if not run_dir.name.startswith("run_") or run_dir.parent.name != "runs":
        raise ValueError("Select run_details.json from its original pilot runs/run_... folder, or drag the original CSV file")
    return _input_from_record(record, run_dir.parent.parent)


def _resolve_existing_input(selected: Path) -> Dict[str, Any]:
    if selected.is_file():
        if selected.name == "run_details.json":
            return _explicit_record_input(selected)
        if selected.suffix.lower() == ".csv":
            return {"csv_path": selected, "cache_dir": None,
                    "pilot_dir": None, "run_id": None}
        raise ValueError("Select the original .csv file, the prior pilot folder, or its run_details.json")
    if not selected.is_dir():
        raise ValueError("That path is not an existing local file or folder")
    if (selected / "run_details.json").is_file():
        return _explicit_record_input(selected / "run_details.json")
    for _name, _mtime_ns, record_path, pilot_dir in _record_candidates(selected):
        try:
            return _input_from_record(record_path, pilot_dir)
        except (ValueError, OSError, RuntimeError):
            continue
    raise ValueError("No usable IBM data-pilot record was found inside that folder; drag the original HI-Small_Trans.csv file instead")


def resolve_input(path: Any) -> Dict[str, Any]:
    """Resolve exactly the selected CSV, prior pilot folder, or saved run.

    An explicit selection never falls back to another pilot directory. For a
    pilot folder, its newest usable matching saved data run supplies the input.
    Inaccessible paths produce a local input error rather than a traceback.
    """
    try:
        return _resolve_existing_input(_resolved(path))
    except (OSError, RuntimeError) as exc:
        raise ValueError("Could not inspect the selected local file or folder: %s" % exc) from exc
